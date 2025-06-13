import platform
import socket
import threading
import time
from typing import List

import j1939
from j1939.j1939_21 import J1939_21
from j1939.message_id import MessageId
from j1939.parameter_group_number import ParameterGroupNumber

from te.interface.j1939.comm_interface.j1939_ca import J1939CA
from te.interface.j1939.comm_interface.j1939_message import Message
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN


class CustomJ1939(J1939_21):

    def __init__(self, *args, **kwargs):
        self.__notifyTheseAlso = kwargs.get("notify_these_also")
        self.__notifyCallback = args[2]  # _notify_subscribers
        super().__init__(*args)
        self.multi_packet_msg_sent = threading.Event()

    def notify(self, can_id, data, timestamp):
        super().notify(can_id, data, timestamp)
        # now notify any received messages that we're interested in, but which the regular J1939_21 class omits:
        mid = MessageId(can_id=can_id)
        pgn = ParameterGroupNumber()
        pgn.from_message_id(mid)
        pgn_value = pgn.value & 0x1FF00
        if pgn_value in self.__notifyTheseAlso:
            dest_address = pgn.pdu_specific
            self.__notifyCallback(mid.priority, pgn_value, mid.source_address, dest_address, timestamp, data)

    def async_job_thread(self, now):
        for bufid in list(self._snd_buffer):
            buf = self._snd_buffer[bufid]
            if buf['state'] == self.SendBufferState.TRANSMISSION_FINISHED:
                self.multi_packet_msg_sent.set()
        return super().async_job_thread(now)


class CustomECU(j1939.ElectronicControlUnit):

    def __init__(self, **kwargs):
        self.max_cmdt_packets = kwargs.get('max_cmdt_packets', 0xFF)
        self.minimum_tp_rts_cts_dt_interval = kwargs.get('minimum_tp_rts_cts_dt_interval', None)
        self.minimum_tp_bam_dt_interval = kwargs.get('minimum_tp_bam_dt_interval', None)
        super().__init__(**kwargs)

    def _async_job_thread(self):
        del self.j1939_dll
        self.j1939_dll = CustomJ1939(self.send_message,
                                     self._job_thread_wakeup,
                                     self._notify_subscribers,
                                     self.max_cmdt_packets,
                                     self.minimum_tp_rts_cts_dt_interval,
                                     self.minimum_tp_bam_dt_interval,
                                     self._is_message_acceptable,
                                     notify_these_also=[
                                         ParameterGroupNumber.PGN.ADDRESSCLAIM,
                                         ParameterGroupNumber.PGN.REQUEST,
                                         ParameterGroupNumber.PGN.TP_CM,
                                         ParameterGroupNumber.PGN.DATATRANSFER
                                     ])
        super()._async_job_thread()

    def connect(self, *args, **kwargs):
        bus = super().connect(*args, **kwargs)
        if platform.system() == 'Linux':
            self._bus.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1785)
        return bus


class J1939CAUniversal(J1939CA):

    def __init__(self, interface_name: str, address: int = 0xF2, bitrate: int = 500000):
        super().__init__(interface_name, address)
        self.bitrate = bitrate
        self.bus_type = 'socketcan'

        if platform.system() == 'Windows':
            if 'PCAN' not in self.interface_name:
                raise ValueError('Only PCAN interfaces are supported on Windows.')
            self.bus_type = 'pcan'

        self.name = j1939.Name(
            arbitrary_address_capable=0,
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=1,
            vehicle_system=1,
            function=1,
            function_instance=1,
            ecu_instance=1,
            manufacturer_code=666,
            identity_number=1234567
        )
        self._ca = j1939.ControllerApplication(self.name, self.address)
        self._ecu: CustomECU = CustomECU(minimum_tp_rts_cts_dt_interval=0.00015)
        self.setup_bus()

    def setup_bus(self):
        self._ecu.connect(bustype=self.bus_type, channel=self.interface_name, bitrate=self.bitrate)
        self._ecu.add_ca(controller_application=self._ca)
        self._ca.subscribe(self._recv_msg)
        self._ca.start()

        # Wait for the address claim to finish
        timeout = time.time() + 2
        while time.time() < timeout:
            if self._ca.state == self._ca.State.NORMAL:
                break
        if self._ca.state != self._ca.State.NORMAL:
            raise RuntimeError('Could not address claim')

        self._state = self.State.READY
        # Update our internal address to reflect the address claim
        self.address = self._ca.device_address

    def disconnect(self):
        if self._state == self.State.DISCONNECTED:
            return  # Already disconnected
        self._ca.stop()
        self._ecu.disconnect()
        self._state = self.State.DISCONNECTED

    def send_to(self, pgn: J1939PGN, dest_address: int, data: bytes, timeout: float = 5.0) -> int:
        data_len = len(data)
        self._ecu.j1939_dll.multi_packet_msg_sent.clear()
        sent = self._ca.send_pgn(pgn.dp(), pgn.pf(), dest_address, 6, list(data))
        self._log_msg(Message((self.interface_name, pgn.dp(), pgn.v, self.address), data), prefix='sent')
        if sent and data_len <= 8:
            return data_len
        if sent and self._ecu.j1939_dll.multi_packet_msg_sent.wait(timeout):
            return data_len
        return 0

    def _recv_msg(self, priority: int, pgn: int, source: int, _: int, data: List[int]) -> None:
        msg = Message(address=(self.interface_name, priority, pgn, source), data=bytes(data), timestamp=time.time())
        self._log_msg(msg, prefix='recv')

        self._add_new_device_from_address_claim(msg)

        # Put the message in the correct queue
        self._recv_queue[msg.sa].put(msg)
