import logging
import os
import platform
import time
from enum import Enum
from typing import List, Any, Union, Callable, Iterable, Optional

from te.interface import TouchEncoder, UpdateProgressCB
from te.interface.common import ProjectInfo, Authentication, Update, Status
from te.interface.j1939 import j1939_messages as messages
from te.interface.j1939.comm_interface import J1939CA, J1939StandardPGN, J1939Name
from te.interface.j1939.comm_interface.j1939_ca_linux import J1939CALinux
from te.interface.j1939.comm_interface.j1939_ca_universal import J1939CAUniversal
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN
from te.interface.j1939.j1939_guide import J1939GUIDEInterface
from te.interface.j1939.j1939_te_statics import TePGN, AckCode

log = logging.getLogger('J1939 TE')


class ConfigureJ1939NameSelector(Enum):
    INDUSTRY_GROUP = 1
    VEHICLE_SYSTEM_INSTANCE = 2
    VEHICLE_SYSTEM = 3
    FUNCTION = 5
    FUNCTION_INSTANCE = 6
    ECU_INSTANCE = 7


class J1939TouchEncoder(TouchEncoder):
    NAME = 'J1939 Touch Encoder'
    PF_PDU2_MIN = 0xF0
    MTU = 1785
    TM_TIMEOUT = 250

    def __init__(self, can_iface: str, address: int, name: J1939Name, ca: Union[J1939CA, int] = 0x11):
        super().__init__()
        self._can_iface = can_iface
        self.address = address & 0xff
        self.name: J1939Name = name

        self.ca: J1939CA = ca
        system_os = platform.system()
        if isinstance(ca, int):
            if system_os == 'Linux':
                self.ca = J1939CALinux(interface_name=self._can_iface, address=ca)
            elif system_os == 'Windows':
                self.ca = J1939CAUniversal(interface_name=self._can_iface, address=ca)
            else:
                raise Exception(f'Unsupported operating system: {system_os}')
        elif ca and not (isinstance(ca, J1939CALinux) or isinstance(ca, J1939CAUniversal)):
            raise ValueError('ca must be an instance of J1939CA or int')

        self.guide: J1939GUIDEInterface = J1939GUIDEInterface(te=self)

    @property
    def interface(self) -> str:
        return f'{self._can_iface}:{hex(self.address)}'

    @property
    def in_utility_app(self) -> bool:
        status = self.set_raw_input_event(True)
        return status == Status.NACK

    def disconnect(self):
        # Clean up socket
        self.ca.disconnect()

    def send_command(self, command: List[int]) -> int:
        return self.ca.send_to(J1939StandardPGN.PROPRIETARY_A.value, self.address, bytes(command))

    def await_res(self, expected_res: Iterable[Callable[[tuple, bytes, Optional[int]], Any]] = None,
                  timeout: float = 1.0, timestamp: Optional[float] = None) -> Any:
        msg = None
        time_now = time.time()
        timeout_end = time_now + timeout
        while time_now < timeout_end and not msg:
            msg = self.ca.recv_msg(timeout=timeout_end - time_now)
            # Skip messages with old timestamp
            if msg and timestamp and msg.timestamp < timestamp:
                msg = None
            if msg and expected_res:
                # Set the res to None if the message is not what we expected
                parsed_msg = None
                for m in expected_res:
                    try:
                        parsed_msg = m(msg.address, msg.data, self.address)
                        break
                    except ValueError:
                        continue
                    except TypeError:
                        continue
                msg = parsed_msg
            time_now = time.time()
        return msg

    def authenticate(self, clearance: Authentication.Clearance) -> Status:
        self.send_command([self.Commands.ST_AUTH, clearance.value] + list(TePGN.AUTHENTICATION.value.to_bytes()))

        msg = self.await_res(expected_res=[messages.AuthMsg])
        if msg is None:
            return Status.ERROR
        if msg.auth_state == Authentication.State.COMPLETE:
            return Status.SUCCESS
        if msg.auth_state != Authentication.State.CHALLENGE:
            return Status.AUTH_REQUEST_FAILED

        # Complete the challenge
        response = Authentication.secret(clearance, self.ca.address, msg.challenge).to_bytes(4, 'little')
        self.ca.send_to(TePGN.AUTHENTICATION.value, self.address,
                        bytes([Authentication.State.RESPONSE.value]) + response)

        msg = self.await_res(expected_res=[messages.AuthMsg])
        if msg is None or msg.auth_state != Authentication.State.COMPLETE:
            return Status.AUTH_CHALLENGE_FAILED

        # self.auth_clearance = clearance
        return Status.SUCCESS

    def refresh_version_info(self) -> Status:
        status = super().refresh_version_info()
        if status != Status.SUCCESS:
            return status

        # Version
        self.ca.send_to(J1939StandardPGN.PGN_REQUEST.value, self.address,
                        J1939StandardPGN.SOFTWARE_ID.value.to_bytes())
        msg = self.await_res(expected_res=[messages.SoftwareIDMsg])

        if msg:
            self.version = msg.version
            return Status.SUCCESS
        return Status.ERROR

    def refresh_hardware_info(self) -> Status:
        super().refresh_hardware_info()
        msg = self.await_res(expected_res=[messages.HardwareIDMsg])
        if msg:
            self.hardware_id = msg.hardware_id.name
            return Status.SUCCESS
        return Status.ERROR

    def refresh_project_info(self) -> Status:
        super().refresh_project_info()
        msg = self.await_res(expected_res=[messages.ProjectInfoMsg])
        if msg:
            self.project_info = ProjectInfo.from_bytes(msg.project_info)
            return Status.SUCCESS
        return Status.ERROR

    def set_brightness(self, level: int, store: bool = False) -> Status:
        # Super will send the brightness command
        super().set_brightness(level, store)
        msg = self.await_res(expected_res=[messages.AckMsg])
        if msg and msg.ack_code == AckCode.OK:
            return Status.SUCCESS
        return Status.ERROR

    def set_raw_input_event(self, enable: bool, pgn: Optional[Union[int, J1939PGN]] = None) -> Status:
        """
        Enable or disable the raw input event.
        :param enable:
        :param pgn: PGN for RIE packets
        :return:
        """
        pgn_bytes = [0x00, 0x00, 0x00]
        if pgn:
            if isinstance(pgn, int):
                pgn = J1939PGN(pgn)
            pgn_bytes = pgn.to_bytes()
        self.send_command([self.Commands.RIE, int(enable)] + list(pgn_bytes))
        msg = self.await_res(expected_res=[messages.AckMsg])
        if msg:
            if msg.ack_code == AckCode.OK:
                return Status.SUCCESS
            if msg.ack_code == AckCode.NACK:
                return Status.NACK
        return Status.ERROR

    def restart(self, to_utility: bool = False, wait: bool = True, authenticate: bool = False) -> Status:
        # Send restart command from the parent method
        status = super().restart(to_utility, wait, authenticate)
        if status != Status.SUCCESS:
            return status

        # Wait for restart ack
        msg = self.await_res(expected_res=[messages.RestartAckMsg], timeout=1, timestamp=time.time())
        if not msg:
            return Status.ERROR
        if msg.ack_code == AckCode.ACCESS_DENIED:
            return Status.ACCESS_DENIED
        if msg.ack_code != AckCode.OK:
            return Status.ERROR

        # Wait for the device to reboot
        if wait:
            msg = self.await_res(expected_res=[messages.AddressClaimMsg], timeout=self.RESTART_TIMEOUT)
            if not msg:
                return Status.RESTART_TIMEOUT
            self.address = msg.sa
            self.name = msg.j1939_name
        return Status.SUCCESS

    def configure_j1939_name(self, selector: ConfigureJ1939NameSelector, value: int,
                             authenticate: bool = False) -> Status:
        """
        Configure J1939 Name fields via the selector and value.
        Note: Servie Tool Authentication is required for this operation.

        :param selector: ConfigureJ1939NameSelector
        :param value: int
        :param authenticate: bool
        :return: Status
        """
        if authenticate:
            status = self.authenticate(Authentication.Clearance.SERVICE_TOOL)
            if status != Status.SUCCESS:
                return status

        self.send_command([self.Commands.CONFIGURE_NAME, selector.value] + list(value.to_bytes(3, 'little')))

        msg = self.await_res(expected_res=[messages.AckMsg])
        if not msg or msg.ack_code == AckCode.CANT_RESPOND:
            return Status.ERROR
        if msg.ack_code == AckCode.NACK:
            return Status.NACK
        if msg.ack_code == AckCode.ACCESS_DENIED:
            return Status.ACCESS_DENIED
        status = self.restart()
        return status

    def update(self, filepath: str, progress_cb: UpdateProgressCB = lambda *_, **__: None,
               session_pgn: TePGN = TePGN.LIVE_UPDATE) -> Update.Status:
        """
        session_pgn: Session PGN used only by J1939 devices
        """
        # Track the internal update state
        update_state = Update.State.UPDATE_REQUEST
        # Return status of the update
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
            msg = self.ca.recv_msg(timeout=0)

            if update_state == Update.State.FILE_UPLOAD and file_stream:
                payload = file_stream.read(self.MTU)
                if len(payload) != 0:
                    sz = self.ca.send_to(session_pgn.value, self.address, payload)
                    # Exit since there was an error sending payload
                    if sz != len(payload):
                        update_state = Update.State.UPLOAD_ERROR
                        break
                    upload_progress += sz
                    progress_cb(update_state, completed=upload_progress, total=file_size)
                else:  # EOF
                    file_stream.close()
                    file_stream = None
                    # Due to possible buffering in can subsystem, the remote end might have not received all data
                    # yet.
                    # We can't possibly know the optimal value for timeout.
                    # Lets at least set it to a minute so that we do not keep hanging forever in case of transfer
                    # issue on the remote end.
                    task_timeout = time_now + 60

            match update_state:
                case Update.State.UPDATE_REQUEST:
                    progress_cb(update_state)

                    update_type = Update.ComponentType.from_filename(filepath)
                    if update_type == Update.ComponentType.UNKNOWN:
                        progress_cb(Update.State.UPDATE_REJECTED)
                        return Update.Status.ERROR
                    file_size_int = [x for x in file_size.to_bytes(3, 'little')]
                    self.send_command([self.Commands.LIVE_UPDATE, update_type.value] + file_size_int +
                                      list(session_pgn.value.to_bytes()))

                    update_state = Update.State.UPDATE_CONFIRMATION
                    # We should receive res from TE within one second
                    task_timeout = time_now + 1
                case Update.State.UPDATE_CONFIRMATION:
                    progress_cb(update_state)
                    if not msg:
                        continue

                    # TE did not ack live update command
                    try:
                        msg = messages.UpdateAckMsg(msg.address, msg.data, self.address)
                    except ValueError:
                        continue

                    # Reset timer
                    task_timeout = update_timeout
                    if msg.status == 0:
                        file_stream = open(filepath, 'rb', self.MTU)
                        upload_progress = 0
                        progress_cb(update_state, completed=upload_progress, total=file_size)
                        update_state = Update.State.FILE_UPLOAD
                    elif msg.status == 2:
                        update_state = Update.State.UPDATE_REJECTED
                    elif msg.status == 3:
                        update_state = Update.State.DEVICE_BUSY
                    else:
                        update_state = Update.State.ERROR
                    progress_cb(update_state)

                case Update.State.FILE_UPLOAD:
                    if not msg:
                        continue
                    try:
                        msg = messages.UpdateStatusMsg(msg.address, msg.data, self.address, session_pgn.value)
                    except ValueError:
                        continue

                    # Reset timer
                    task_timeout = update_timeout
                    if msg.err != Update.UploadError.OK:
                        update_state = Update.State.UPLOAD_ERROR
                        break
                    update_state = Update.State.UPDATING
                    # Wait max of 10 seconds for update to start
                    task_timeout = time_now + 10

                case Update.State.UPDATING:
                    if not msg:
                        continue
                    try:
                        msg = messages.UpdateStatusMsg(msg.address, msg.data, self.address, session_pgn.value)
                    except ValueError:
                        continue

                    if msg.status_type == Update.StatusType.COMPONENT:
                        task_timeout = time_now + 60
                        if msg.component_status == Update.ComponentStatus.PROGRESS:
                            update_state_comp = Update.State.from_component_type(msg.component_type)
                            progress_cb(update_state_comp, completed=msg.component_progress, total=100)
                    elif msg.status_type == Update.StatusType.UPDATE:
                        update_status = msg.update_status
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
