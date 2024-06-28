import queue
import time
from typing import Dict, Optional, List

import hid as hidapi

from te.interface.hid.comm_interface import HIDInterface
from te.interface.hid.hid_reports import BaseReport


class HIDInterfaceWin(HIDInterface):
    def __init__(self, hid_iface: List[Dict]):
        self._sw_ver_iface: Optional[Dict] = None
        self._rie_iface_1_iface: Optional[Dict] = None
        self._rie_iface_2_iface: Optional[Dict] = None
        self._update_iface: Optional[Dict] = None

        self._sw_ver: Optional[hidapi.device] = None
        self._rie_iface_1: Optional[hidapi.device] = None
        self._rie_iface_2: Optional[hidapi.device] = None
        self._update: Optional[hidapi.device] = None

        super().__init__(hid_iface)

    def _get_log_msg_rpt_type(self, dev: hidapi.device):
        rpt_type_map = {
            self.cmd: 'command',
            self._sw_ver: 'sw-ver',
            self._rie_iface_1: 'rie-1',
            self._rie_iface_2: 'rie-2',
            self._update: 'update',
            self.widget: 'widget'
        }
        return rpt_type_map[dev]

    def connect(self):
        """
        Open communications with this HID device.
        :return:
        """
        for i_face in self._hid_iface:
            i_face_num = i_face['interface_number']
            match i_face_num:
                case 0:
                    path = str(i_face['path'])
                    if 'Col01' in path:
                        self.cmd_iface = i_face
                    elif 'Col02' in path:
                        self._sw_ver_iface = i_face
                    elif 'Col03' in path:
                        self._rie_iface_1_iface = i_face
                    elif 'Col04' in path:
                        self._rie_iface_2_iface = i_face
                    elif 'Col05' in path:
                        self._update_iface = i_face
                case 1:
                    self._widget_iface = i_face
                case _:
                    continue

        def create_device(_path: bytes) -> hidapi.device:
            dev = hidapi.device()
            dev.open_path(_path)
            dev.set_nonblocking(True)  # This helps hidapi from freezing in windows
            return dev

        self.cmd = create_device(self.cmd_iface['path'])
        self._sw_ver = create_device(self._sw_ver_iface['path'])
        self._rie_iface_1 = create_device(self._rie_iface_1_iface['path'])
        self._rie_iface_2 = create_device(self._rie_iface_2_iface['path'])
        self._update = create_device(self._update_iface['path'])

        self.widget = None
        if self._widget_iface:
            self.widget = create_device(self._widget_iface['path'])

        self._recv_thread_state = self.RecvThreadState.RUNNING
        self._recv_thread.start()

    def disconnect(self):
        """
        Close open connection to the HID interface.
        :return:
        """
        self._recv_thread_state = self.RecvThreadState.STOPPED
        self._recv_thread.join()

        def close_device(dev: Optional[hidapi.device]):
            if dev:
                dev.close()

        close_device(self.cmd)
        close_device(self._sw_ver)
        close_device(self._rie_iface_1)
        close_device(self._rie_iface_2)
        close_device(self._update)
        close_device(self.widget)

    def _recv_rpt(self):
        """
        Receive reports from the command and widget interfaces and place them in the receive queue.
        Runs in background thread.
        :return:
        """
        while self._recv_thread_state != self.RecvThreadState.STOPPED:
            for hid_func in [self.cmd, self.widget, self._rie_iface_1, self._rie_iface_2, self._update]:
                if hid_func is None:
                    continue
                res = hid_func.read(self.MAX_REPORT_SIZE)
                if res:
                    self._log_msg(res, prefix='recv', rpt_type=hid_func)
                    if hid_func in [self.cmd, self.widget]:
                        self._recv_queue.put(BaseReport(res, timestamp=time.time()))

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
        self._log_msg(report_id, prefix='sent', rpt_type=self._sw_ver)
        report = self._sw_ver.get_feature_report(report_id, 7)
        self._log_msg(report, prefix='recv', rpt_type=self._sw_ver)
        return report

    def send_update_payload(self, payload: bytes):
        """
        Send the payload to the cmd interface for SW update.
        :param payload:
        :return:
        """
        return self.send(self._update, payload)
