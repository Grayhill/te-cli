import logging
from enum import Enum
from typing import List, TypeAlias, Any, Optional

from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN

_Address: TypeAlias = tuple[Any, ...]


class Message:
    address: _Address
    data: bytes

    def __init__(self, address: _Address, data: bytes, timestamp: Optional[float] = None) -> None:
        self.address = address
        self.data = data
        self.timestamp = timestamp

    def __str__(self) -> str:
        return self.can_id.upper() + ' ' + self.data.hex(' ').upper()

    @property
    def sa(self) -> int:
        return self.address[3]

    @property
    def pgn(self) -> J1939PGN:
        return J1939PGN(self.address[2])

    @property
    def can_id(self) -> str:
        priority = 6
        can_id_bytes = bytes([priority << 2 | self.pgn.dp(), self.pgn.pf(), self.pgn.ps(), self.sa])
        return can_id_bytes.hex()

    @property
    def length(self) -> int:
        return len(self.data)


class J1939CA:

    class State(Enum):
        INIT = 0
        ADDRESS_CLAIM = 1
        CANNOT_CLAIM = 2
        READY = 3
        NOT_READY = 4
        ERROR = 5

    MAX_DATA_SIZE = 1785

    def __init__(self, interface_name: str, address: int):
        self.interface_name = interface_name
        self.address = address

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

    def send_to(self, pgn: J1939PGN, dest_address: int, data: bytes) -> int:
        """
        Send a message to the device
        :param pgn:
        :param dest_address:
        :param data:
        :return: Num of bytes sent
        """
        raise NotImplementedError()

    def send_globally(self, pgn: J1939PGN, data: bytes):
        """
        Send a message to all the devices connected to the can bus
        TODO: Remove if not needed.
        :param pgn:
        :param data:
        :return:
        """
        raise NotImplementedError()

    def recv_msg(self, timeout=0.1) -> Optional[Message]:
        """
        Receive a message from the device
        :param timeout: Timeout to wait for a message
        :return: Message
        """
        raise NotImplementedError()

    def scan_for_devices(self, timeout=2.0) -> List[Message]:
        """
        Send address claimed message to scan for devices connected to the bus.
        :param timeout: Timout for scanning devices
        :return: List of Messages (device info)
        """
        raise NotImplementedError()
