import logging
import os
import platform
import time
from typing import List, Any, Iterable, Callable, Optional

import hid as hidapi

from te.interface import TouchEncoder, UpdateProgressCB
from te.interface.common import Authentication, Version, Update, Status
from te.interface.hid import hid_reports as reports
from te.interface.hid.comm_interface import HIDInterface, HIDInterfaceWin
from te.interface.hid.hid_guide import HIDGUIDEInterface
from te.interface.hid.hid_reports import AckReportCode, ReportIDs
from te.interface.hid.hid_te_statics import ContextIDs
from te.interface.hid.utils import hot_plug_utility

log = logging.getLogger('HID TE')


class HIDTouchEncoder(TouchEncoder):
    NAME = 'HID Touch Encoder'

    VENDOR_ID = 0x1658
    PRODUCT_ID = 0x0060

    MAX_REPORT_SIZE = 1024
    MAX_UPLOAD_SIZE = MAX_REPORT_SIZE - 3
    TM_TIMEOUT = 1

    def __init__(self, hid_iface, serial_number=None):
        super().__init__()
        self._serial_number = serial_number
        system_os = platform.system()
        if system_os == 'Linux':
            self.hid: HIDInterface = HIDInterface(hid_iface)
        elif system_os == 'Windows':
            self.hid: HIDInterfaceWin = HIDInterfaceWin(hid_iface)
        else:
            raise Exception(f'Unsupported operating system: {system_os}')

        self.guide: HIDGUIDEInterface = HIDGUIDEInterface(te=self)

    @property
    def interface(self) -> str:
        return f'usb:{self._serial_number}'

    @property
    def in_utility_app(self) -> bool:
        return self.hid.widget is None

    def disconnect(self):
        # Disconnect hid interface from the device
        self.hid.disconnect()

    def send_command(self, command: List[int]) -> int:
        return self.hid.send(self.hid.cmd, [0x02] + command)

    def send_widget_command(self, command: List[int]) -> int:
        """
        Send a command to the device using interface #1/widget
        :param command:
        :return:
        """
        if not self.hid.widget:
            return 0
        return self.hid.send(self.hid.widget, command)

    def await_res(self, expected_res: Iterable[Callable[[bytes | Iterable[int]], Any]] = None,
                  timeout: float = 1.0, timestamp: Optional[float] = None) -> Any:
        res = None
        time_now = time.time()
        timeout_end = time_now + timeout
        while time_now < timeout_end and not res:
            res = self.hid.recv_rpt(timeout=timeout_end-time_now)
            # Skip messages with the old timestamp
            if res and timestamp and res.timestamp < timestamp:
                res = None
            if res and expected_res:
                # Set the res to None if the message is not what we expected
                parsed_res = None
                for m in expected_res:
                    try:
                        parsed_res = m(res.raw_report)
                        break
                    except ValueError:
                        continue
                    except TypeError:
                        continue
                res = parsed_res
            time_now = time.time()
        return res

    def authenticate(self, clearance: Authentication.Clearance) -> Status:
        self.send_command([self.Commands.ST_AUTH, clearance.value, ContextIDs.AUTH, 0x00, 0x00, 0x00, 0x00, 0x00])
        auth_report = self.await_res(expected_res=[reports.AuthReport])
        if not auth_report:
            return Status.ERROR
        if auth_report.auth_state == Authentication.State.COMPLETE:
            return Status.SUCCESS
        if auth_report.auth_state != Authentication.State.CHALLENGE:
            return Status.AUTH_REQUEST_FAILED

        response = Authentication.secret(clearance, 0x1337, auth_report.challenge)
        report = reports.ContextSensitiveReport.from_fragments(ContextIDs.AUTH, Authentication.State.RESPONSE.value,
                                                               response.to_bytes(4, 'little'))
        self.hid.send(self.hid.cmd, report.raw_report)

        auth_report = self.await_res(expected_res=[reports.AuthReport])
        if not auth_report or auth_report.auth_state != Authentication.State.COMPLETE:
            return Status.AUTH_CHALLENGE_FAILED

        # self.auth_clearance = clearance
        return Status.SUCCESS

    def refresh_version_info(self) -> Status:
        status = super().refresh_version_info()
        if status != Status.SUCCESS:
            return status

        def report_to_version(report_id):
            try:
                report_out = self.hid.get_sw_ver_report(report_id)
            except OSError:
                return 'Not Found'
            major = int.from_bytes(report_out[1:3], 'little')
            minor = int.from_bytes(report_out[3:5], 'little')
            patch = int.from_bytes(report_out[5:7], 'little')
            return f'{major}.{minor}.{patch}'

        firmware = report_to_version(ReportIDs.FW_VER)
        bootloader = report_to_version(ReportIDs.BL_VER)
        project = report_to_version(ReportIDs.PROJ_VER)
        self.version = Version(firmware, bootloader, project)
        return Status.SUCCESS

    def refresh_hardware_info(self) -> Status:
        super().refresh_hardware_info()
        hw_ack = self.await_res(expected_res=[reports.HardwareIDReport])
        if hw_ack and hw_ack.code == AckReportCode.OK:
            self.hardware_id = hw_ack.hardware_id.name
            return Status.SUCCESS
        return Status.ERROR

    def refresh_project_info(self) -> Status:
        super().refresh_project_info()
        proj_ack = self.await_res(expected_res=[reports.ProjectInfoReport])
        if proj_ack and proj_ack.code == AckReportCode.OK:
            self.project_info = proj_ack.project_info
            return Status.SUCCESS
        return Status.ERROR

    def set_brightness(self, level: int, store: bool = False) -> Status:
        # Super will send the brightness command
        super().set_brightness(level, store)
        ack = self.await_res(expected_res=[reports.AckReport])
        if ack and ack.code == AckReportCode.OK:
            return Status.SUCCESS
        return Status.ERROR

    def set_raw_input_event(self, enable: bool) -> Status:
        # Super will send the brightness command
        super().set_raw_input_event(enable)
        ack = self.await_res(expected_res=[reports.AckReport])
        if ack and ack.code == AckReportCode.OK:
            return Status.SUCCESS
        return Status.ERROR

    def restart(self, to_utility: bool = False, wait: bool = True, authenticate: bool = False) -> Status:
        # Send restart command from the parent method
        status = super().restart(to_utility, wait, authenticate)
        if status != Status.SUCCESS:
            return status
        ack = self.await_res(expected_res=[reports.AckReport], timeout=5)
        if not ack:
            return Status.ERROR
        if ack.code == AckReportCode.ACC_DENIED:
            return Status.ACCESS_DENIED
        if ack.code == AckReportCode.OK:
            if wait:
                return self._await_restart(timeout=self.RESTART_TIMEOUT)
            return Status.SUCCESS
        return Status.ERROR

    def _await_restart(self, timeout=10) -> Status:
        """
        Disconnect TE from the HID interface, wait for a device to restart via hotplug event, and reconnect TE
        :param timeout: Max time (s) to wait
        :return:
        """
        self.hid.disconnect()

        device = None
        # Windows does not have the hotplug utility implemented, so we will poll and wait for the device to come online.
        if platform.system() == "Windows":
            timeout_end = time.time() + timeout
            while time.time() < timeout_end and not device:
                time.sleep(0.5)  # Wait for the device to disconnect and restart
                for i_face in hidapi.enumerate(vendor_id=HIDTouchEncoder.VENDOR_ID,
                                               product_id=HIDTouchEncoder.PRODUCT_ID):
                    if self._serial_number == i_face['serial_number']:
                        device = i_face
                        break
        else:
            devices = hot_plug_utility.wait_hotplug_event(
                [hot_plug_utility.DevDsc(self.hid.cmd_iface['vendor_id'], self.hid.cmd_iface['product_id'])],
                timeout)
            for d in devices:
                if self._serial_number == d.sn:
                    device = d
                    break
        if device:
            self.hid.reconnect()
            return Status.SUCCESS
        return Status.RESTART_TIMEOUT

    def update(self, filepath: str, progress_cb: UpdateProgressCB = lambda *_, **__: None) -> Update.Status:
        update_state = Update.State.UPDATE_REQUEST
        update_status = Update.Status.ERROR

        filepath_stats = os.stat(filepath)
        file_size = filepath_stats.st_size
        file_stream = None

        upload_progress = 0

        time_now = time.time()
        update_timeout = time_now + self.UPDATE_TIMEOUT
        task_timeout = update_timeout
        while time_now < task_timeout and time_now < update_timeout:
            time_now = time.time()
            report = self.hid.recv_rpt(timeout=0)

            match update_state:
                case Update.State.UPDATE_REQUEST:
                    progress_cb(update_state)

                    update_type = Update.ComponentType.from_filename(filepath).value
                    file_size_int = [x for x in file_size.to_bytes(3, 'little')]
                    self.send_command([self.Commands.LIVE_UPDATE, update_type] + file_size_int + [0x00, 0x00, 0x00])

                    update_state = Update.State.UPDATE_CONFIRMATION
                    # We should receive res from TE within one second
                    task_timeout = time_now + 1
                case Update.State.UPDATE_CONFIRMATION:
                    progress_cb(update_state)
                    if not report:
                        continue

                    # TE did not ack live update command
                    try:
                        ack_report = reports.UpdateAckMsg(report.raw_report)
                    except ValueError:
                        continue

                    # Reset timer
                    task_timeout = update_timeout
                    if ack_report.status == 1:
                        update_state = Update.State.FILE_UPLOAD
                        file_stream = open(filepath, 'rb', self.MAX_UPLOAD_SIZE)
                        upload_progress = 0
                    else:
                        update_state = Update.State.UPDATE_REJECTED
                    progress_cb(update_state)

                case Update.State.FILE_UPLOAD:
                    if report:
                        try:
                            status_report = reports.UpdateStatusMsg(report.raw_report)
                        except ValueError:
                            continue

                        if status_report.err != Update.UploadError.OK:
                            update_state = Update.State.UPLOAD_ERROR
                            break
                        update_state = Update.State.UPDATING

                    if file_stream:
                        payload = file_stream.read(self.MAX_UPLOAD_SIZE)
                        if len(payload) > 0:
                            report_to_send = (bytes([ReportIDs.UPDATE_DATA]) + len(payload).to_bytes(2, 'little')
                                              + payload)
                            sent = self.hid.send_update_payload(report_to_send)
                            if sent != len(report_to_send):
                                update_state = Update.State.UPLOAD_ERROR
                                break

                            upload_progress += len(payload)
                            progress_cb(update_state, completed=upload_progress, total=file_size)
                        else:  # Done
                            file_stream.close()
                            file_stream = None

                            # Wait max of 10 seconds for update to start
                            task_timeout = time_now + 60

                case Update.State.UPDATING:
                    if not report:
                        continue
                    try:
                        status_report = reports.UpdateStatusMsg(report.raw_report)
                    except ValueError:
                        continue

                    if status_report.status_type == Update.StatusType.COMPONENT:
                        task_timeout = time_now + 60
                        if status_report.component_status == Update.ComponentStatus.PROGRESS:
                            update_state_comp = Update.State.from_component_type(status_report.component_type)
                            progress_cb(update_state_comp, completed=status_report.component_progress, total=100)
                    elif status_report.status_type == Update.StatusType.UPDATE:
                        update_status = status_report.update_status
                        if update_status != Update.Status.ONGOING:
                            if update_status.value >= Update.Status.SUCCESS.value:
                                update_state = Update.State.SUCCESS
                            else:
                                update_state = Update.State.ERROR
                            break
                case _:
                    break

        # Timed out
        if time_now > task_timeout or time_now > update_timeout:
            return Update.Status.TIMEOUT

        # Update completed. Restart the device.
        if update_state == Update.State.SUCCESS and update_status != Update.Status.SUCCESS_UPTODATE:
            progress_cb(Update.State.REBOOTING)
            self.restart(wait=True)

        return update_status
