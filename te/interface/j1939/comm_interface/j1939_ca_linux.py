import queue
import select
import socket
import time
from enum import Enum, auto
from threading import Thread
from typing import List, Optional

from te.interface.j1939.j1939_messages import AddressClaimMsg
from te.interface.j1939.comm_interface import J1939StandardPGN, J1939CA, Message
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN


class J1939CALinux(J1939CA):

    class State(Enum):
        INIT = auto()
        ADDRESS_CLAIM = auto()
        CANNOT_CLAIM = auto()
        READY = auto()
        NOT_READY = auto()
        ERROR = auto()
        CLOSE = auto()

    MAX_DATA_SIZE = 1785

    def __init__(self, interface_name: str, address: int):
        super().__init__(interface_name, address)
        self.interface_name = interface_name
        self.address = address
        # self._name = name

        self._recv_queue = queue.Queue()
        self._recv_thread = Thread(target=self._recv_msg, args=())

        self.s = socket.socket(family=socket.PF_CAN, type=socket.SOCK_DGRAM, proto=socket.CAN_J1939)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.state = self.State.INIT

        self.setup_bus()

    def setup_bus(self):
        address_to_claim = (self.interface_name, socket.J1939_NO_NAME, socket.J1939_NO_PGN, self.address)
        self.s.bind(address_to_claim)
        self.state = self.State.READY
        self._recv_thread.start()

    def disconnect(self):
        self.state = self.State.CLOSE
        self._recv_thread.join()
        self.s.close()

    def send_to(self, pgn: J1939PGN, dest_address: int, data: bytes) -> int:
        addr = "", socket.J1939_NO_NAME, int(pgn) & (~0xFF), dest_address
        # Create a new message for logging purposes
        self._log_msg(Message(address=("", socket.J1939_NO_NAME, int(pgn) | dest_address, self.address), data=data),
                      prefix='sent')
        return self.s.sendto(data, addr)

    def send_globally(self, pgn: J1939PGN, data: bytes):
        addr = "", socket.J1939_NO_NAME, int(pgn), socket.J1939_NO_ADDR
        return self.s.sendto(data, addr)

    def _recv_msg(self):
        poll_set = select.poll()
        poll_set.register(self.s.fileno(), select.POLLIN)
        while self.state != self.State.CLOSE:
            poll_res = poll_set.poll(0.1)
            for fd, ev in poll_res:
                if ev & select.POLLIN:
                    data, addr = self.s.recvfrom(self.MAX_DATA_SIZE)
                    msg = Message(data=data, address=addr, timestamp=time.time())
                    self._log_msg(Message(address=addr, data=data), prefix='recv')
                    self._recv_queue.put(msg)
        poll_set.unregister(self.s.fileno())

    def recv_msg(self, timeout=0.1) -> Optional[Message]:
        try:
            msg = self._recv_queue.get(timeout=timeout)
            self._recv_queue.task_done()
            return msg
        except queue.Empty:
            return None

    def scan_for_devices(self, timeout=2.0) -> List[Message]:
        self.send_globally(J1939StandardPGN.PGN_REQUEST.value, J1939StandardPGN.ADDRESS_CLAIMED.value.to_bytes())
        messages = []
        timeout_end = time.time() + timeout
        while time.time() < timeout_end:
            msg = self.recv_msg()
            if not msg:
                continue
            try:
                acm = AddressClaimMsg(msg.address, msg.data)
                messages.append(acm)
            except ValueError:
                continue
        return messages
