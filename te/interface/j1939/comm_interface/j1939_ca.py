import logging
import queue
import threading
import time
from enum import Enum, auto
from queue import Queue
from typing import List, TypeAlias, Any, Optional, Tuple, Dict, Callable

from te.interface.j1939.comm_interface import J1939Name
from te.interface.j1939.comm_interface.j1939_message import Message
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN, J1939StandardPGN
from te.interface.j1939.j1939_messages import AddressClaimMsg

_Address: TypeAlias = tuple[Any, ...]
J1939NewDevCallback: TypeAlias = Callable[[str, J1939Name, int], None]


class J1939CA:

    class State(Enum):
        INIT = auto()
        READY = auto()
        DISCONNECTED = auto()

    MAX_DATA_SIZE = 1785

    def __init__(self, interface_name: str, address: int):
        self.interface_name: str = interface_name
        self.address: int = address
        self._state = self.State.INIT

        # Keep track of devices and their addresses
        self._devices: Dict[J1939Name, int] = {}
        self._recv_queue: Dict[int, Queue[Message]] = {}

        # Callbacks for new devices
        self._new_dev_callback: List[J1939NewDevCallback] = []

        self.logger = logging.getLogger(f'{type(self).__name__}:{self.interface_name}')

    def _log_msg(self, msg: Message, prefix: str = ''):
        """
        Log the message with the prefix
        :param msg:
        :return:
        """
        self.logger.debug('{:<} → {:<8} {:>5} {:<}'.format(prefix, f'{msg.can_id.upper()}',
                                                           f'[{len(msg.data)}]', msg.data.hex(' ').upper()))

    def setup_bus(self):
        """
        Initialize the CAN bus for J1939 communication
        :return:
        """
        raise NotImplementedError()

    def disconnect(self):
        """
        Close connection to CAN bus and the device
        :return:
        """
        raise NotImplementedError()

    def register_new_dev_callback(self, callback: J1939NewDevCallback):
        """
        Register a callback to be called when a new device is detected.
        :param callback:
        :return:
        """
        self._new_dev_callback.append(callback)

    def unregister_new_dev_callback(self, callback: J1939NewDevCallback):
        """
        Deregister a previously registered new device callback.
        :param callback:
        :return:
        """
        self._new_dev_callback.remove(callback)

    def send_to(self, pgn: J1939PGN, dest_address: int, data: bytes) -> int:
        """
        Send a message to the device
        :param pgn:
        :param dest_address:
        :param data:
        :return: Num of bytes sent
        """
        raise NotImplementedError()

    def recv_msg(self, addr: Optional[int] = None, name: Optional[J1939Name] = None, timeout=0.1) -> Optional[Message]:
        """
        Receive a message from the device
        :param addr: Address of the device
        :param name: Name of the device
        :param timeout: Timeout to wait for a message
        :return: Message
        """
        if not addr and not name:
            raise ValueError('Either addr or name must be provided')

            # Return none if the device is not in the list
        addr = self._devices.get(name, addr)
        if not addr or addr not in self._recv_queue:
            return None

        try:
            msg = self._recv_queue[addr].get(timeout=timeout)
            self._recv_queue[addr].task_done()
            return msg
        except queue.Empty:
            return None

    def scan_for_devices(self, timeout=2.0) -> List[Tuple[J1939Name, int]]:
        """
        Send address claimed message to scan for devices connected to the bus.
        :param timeout: Timout for scanning devices
        :return: List of Messages (device info)
        """
        # Clear the devices and queues
        self._devices = {}
        self._recv_queue = {}

        self.send_to(J1939StandardPGN.PGN_REQUEST.value, 0xFF, J1939StandardPGN.ADDRESS_CLAIMED.value.to_bytes())
        time.sleep(timeout)

        devices = []
        for dev_name, dev_addr in self._devices.items():
            devices.append((dev_name, dev_addr))
        return devices

    def _add_new_device_from_address_claim(self, msg: Message):
        """
        Add a new device to the list of devices
        :param msg:
        :return:
        """
        # If address claim message, add a new queue to _recv_queue
        try:
            acm = AddressClaimMsg.from_msg(msg)
            # Remove the old queue if it exists
            if acm.j1939_name in self._devices:
                del self._recv_queue[self._devices[acm.j1939_name]]
            # Add/update the device address and queue
            self._devices[acm.j1939_name] = acm.sa
            self._recv_queue[acm.sa] = Queue()

            # Call the new device callbacks
            for callback in self._new_dev_callback:
                th = threading.Thread(target=callback, args=(self.interface_name, acm.j1939_name, acm.sa))
                th.start()
        except ValueError:
            return  # Ignore non-address claim messages
