import queue
import time
from enum import Enum
from threading import Thread
from typing import Dict, Optional, List, Union

import hid as hidapi
import logging

from te.interface.hid.hid_reports import BaseReport


class HIDInterface:
    MAX_REPORT_SIZE = 1024

    class RecvThreadState(Enum):
        RUNNING = "RUNNING"
        STOPPED = "STOPPED"

    def __init__(self, hid_iface: List[Dict]):
        self._hid_iface = hid_iface
        self.cmd_iface: Optional[Dict] = None
        self._widget_iface: Optional[Dict] = None

        self._parse_hid_iface()

        sn = self.cmd_iface.get('serial_number')
        self.logger = logging.getLogger(f'{type(self).__name__}:{sn}')

        self._recv_queue = queue.Queue()
        self._recv_thread = Thread(target=self._recv_rpt, args=())
        self._recv_thread_state = self.RecvThreadState.STOPPED

        self.cmd: hidapi.device = hidapi.device()
        self.widget: Optional[hidapi.device] = None
        self.aux = []

        self.connect()

    def _parse_hid_iface(self):
        for i_face in self._hid_iface:
            i_face_num = i_face['interface_number']
            match i_face_num:
                case 0:
                    self.cmd_iface = i_face
                case 1:
                    self._widget_iface = i_face
                case _:
                    continue

    def connect(self):
        """
        Open communications with this HID device.
        :return:
        """
        self._parse_hid_iface()

        self.cmd = hidapi.device()
        self.cmd.open_path(self.cmd_iface['path'])
        # This helps hidapi from freezing in windows
        self.cmd.set_nonblocking(True)

        self.widget = None
        if self._widget_iface:
            self.widget = hidapi.device()
            self.widget.open_path(self._widget_iface['path'])
            self.widget.set_nonblocking(True)

        self._recv_thread_state = self.RecvThreadState.RUNNING
        self._recv_thread.start()

    def disconnect(self):
        """
        Close open connection to the HID interface.
        :return:
        """
        self._recv_thread_state = self.RecvThreadState.STOPPED
        self._recv_thread.join()

        self.cmd.close()
        if self.widget:
            self.widget.close()
        if self.aux:
            for a in self.aux:
                a.close()
            self.aux = []

    def reconnect(self):
        """
        Same as connect but enumerates HID devices to look up this device.
        Use this for tasks like hot-plug event.
        :return:
        """
        self.disconnect()
        d_info = []
        for i_face in hidapi.enumerate(vendor_id=self.cmd_iface['vendor_id'], product_id=self.cmd_iface['product_id']):
            sn_match = i_face['serial_number'] == '' or i_face['serial_number'] == self.cmd_iface['serial_number']
            if sn_match:
                d_info.append(i_face)
        if len(d_info) < 1:
            raise LookupError('Device not found')
        self.__init__(d_info)

    def send(self, hid_func: hidapi.device, data: Union[List[int], bytes]) -> int:
        """
        Write data to the specified HID device (either cmd, widget, or aux).
        :param hid_func:
        :param data:
        :return:
        """
        self._log_msg(data, prefix='sent', rpt_type=hid_func)
        if isinstance(data, list):
            data = bytes(data)
        return hid_func.write(data)

    def _recv_rpt(self):
        """
        Receive reports from the command and widget interfaces and place them in the receive queue.
        Runs in a background thread.
        :return:
        """
        while self._recv_thread_state != self.RecvThreadState.STOPPED:
            try:
                for hid_func in [self.cmd, self.widget]:
                    if hid_func is None:
                        continue
                    res = hid_func.read(self.MAX_REPORT_SIZE, timeout_ms=100)
                    if res:
                        self._log_msg(res, prefix='recv', rpt_type=hid_func)
                        self._recv_queue.put(BaseReport(res, timestamp=time.time()))
            except OSError:
                self.logger.error('Device disconnected')
                break

    def recv_rpt(self, timeout=0.1) -> Optional[BaseReport]:
        """
        Get a report from the receive queue, returns None if the queue is empty.
        :param timeout:
        :return:
        """
        try:
            msg = self._recv_queue.get(timeout=timeout)
            self._recv_queue.task_done()
            return msg
        except queue.Empty:
            return None

    def get_sw_ver_report(self, report_id: int) -> bytes:
        """
        Get the feature report from the command interface.
        :param report_id:
        :return:
        """
        self._log_msg(report_id, prefix='sent', rpt_type='sw-ver')
        report = self.cmd.get_feature_report(report_id, 7)
        self._log_msg(report, prefix='recv', rpt_type='sw-ver')
        return report

    def get_input_report(self, report_id: int, size: int) -> bytes:
        """
        Get the input report from the widget interface.
        :param report_id:
        :param size:
        :return:
        """
        if not self.widget:
            return bytes()
        self._log_msg(report_id, prefix='sent', rpt_type=self.widget)
        report = self.widget.get_input_report(report_id, size)
        self._log_msg(report, prefix='recv', rpt_type=self.widget)
        return report

    def send_update_payload(self, payload: bytes):
        """
        Send the payload to the cmd interface for SW update.
        :param payload:
        :return:
        """
        return self.send(self.cmd, payload)

    def _get_log_msg_rpt_type(self, dev: hidapi.device):
        return 'command' if dev == self.cmd else 'widget'

    def _log_msg(self, data: Union[list, int], prefix: str = '', rpt_type: Union[str, hidapi.device] = '') -> None:
        """
        Format and log the message
        :param data:
        :param prefix:
        :param rpt_type:
        :return:
        """
        if rpt_type and isinstance(rpt_type, hidapi.device):
            rpt_type = self._get_log_msg_rpt_type(rpt_type)
        if rpt_type is None:
            rpt_type = ''
        data_str = ''
        if isinstance(data, int):
            data = [data]
        for d in data:
            data_str += f'{d:02x} '.upper()
        self.logger.debug('{:<} → {:<7} {:>6} {:<}'.format(prefix, rpt_type, f'[{len(data)}]', data_str.strip()))
