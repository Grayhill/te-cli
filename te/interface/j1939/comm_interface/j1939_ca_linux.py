import select
import socket
import threading
import time
from enum import Enum, auto
from queue import Queue
from threading import Thread
from typing import Tuple

from te.interface.j1939.comm_interface.j1939_ca import J1939CA
from te.interface.j1939.comm_interface.j1939_message import Message
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN


class ValueEvent:
    def __init__(self):
        self.event = threading.Event()
        self.value = None

    def set(self, value):
        self.value = value
        self.event.set()

    def wait(self, timeout=None):
        self.event.wait(timeout)
        return self.value


class J1939CALinux(J1939CA):

    class State(Enum):
        INIT = auto()
        ADDRESS_CLAIM = auto()
        CANNOT_CLAIM = auto()
        READY = auto()
        NOT_READY = auto()
        ERROR = auto()
        CLOSE = auto()
        DISCONNECTED = auto

    MAX_DATA_SIZE = 1785

    def __init__(self, interface_name: str, address: int):
        super().__init__(interface_name, address)
        self.interface_name = interface_name
        self.address = address
        # self._name = name

        # Thread to receive and send messages
        self._send_queue: Queue[Tuple] = Queue()
        self._recv_thread_stop_event = threading.Event()
        self._recv_thread = Thread(target=self._send_recv_loop, args=(), daemon=True)

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
        if self.state == self.State.DISCONNECTED:
            return
        self.state = self.State.DISCONNECTED

        # # Prepare socket for closing
        self.s.setblocking(False)
        self.s.settimeout(1.0)

        self._recv_thread_stop_event.set()
        self._recv_thread.join()
        self.s.close()

    def send_to(self, pgn: J1939PGN, dest_address: int, data: bytes) -> int:
        addr = "", socket.J1939_NO_NAME, int(pgn) & (~0xFF), dest_address
        # Create a new message for logging purposes
        self._log_msg(Message(address=("", socket.J1939_NO_NAME, int(pgn) | dest_address, self.address), data=data),
                      prefix='sent')

        wait_to_send = ValueEvent()
        self._send_queue.put((data, addr, wait_to_send))
        sent = wait_to_send.wait(timeout=1.0)
        return sent

    def set_priority(self, priority: int) -> None:
        """
        Set the priority of the messages sent by this controller application.
        :param priority:
        :return:
        """
        self.s.setsockopt(socket.SOL_CAN_BASE + socket.CAN_J1939, socket.SO_J1939_SEND_PRIO, priority)

    def _send_recv_loop(self):
        poll_set = select.poll()
        poll_set.register(self.s.fileno(), select.POLLIN | select.POLLOUT)
        while True:
            if self._recv_thread_stop_event.is_set():
                break
            try:
                poll_res = poll_set.poll(25)  # 25 ms timeout
                for fd, ev in poll_res:
                    if ev & select.POLLOUT and not self._send_queue.empty():
                        # Send a message
                        snd_msg = self._send_queue.get(block=False)
                        data, addr, wait_to_send = snd_msg
                        sent = self.s.sendto(data, addr)
                        wait_to_send.set(sent)
                        self._send_queue.task_done()
                    elif ev & select.POLLIN:
                        data, addr = self.s.recvfrom(self.MAX_DATA_SIZE)
                        msg = Message(data=data, address=addr, timestamp=time.time())
                        self._log_msg(Message(address=addr, data=data), prefix='recv')
                        self._add_new_device_from_address_claim(msg)

                        # Put the message in the correct queue
                        if msg.sa in self._recv_queue:
                            self._recv_queue[msg.sa].put(msg)
            except OSError as e:
                self.logger.debug(f'Device disconnected: {e}')
                break
            except KeyError as e:
                self.logger.error(f'Error in send/recv loop: {e}')
                break
        poll_set.unregister(self.s.fileno())
        self.logger.debug('Exiting send/recv loop')
