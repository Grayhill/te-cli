from typing import TypeAlias, Any, Optional

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

    @classmethod
    def from_msg(cls, msg: 'Message') -> 'Message':
        return cls(msg.address, msg.data, msg.timestamp)

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
