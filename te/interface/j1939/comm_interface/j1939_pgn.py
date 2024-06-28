from enum import Enum

from typing import Sequence


class J1939PGN:
    J1939_PF_PDU2_MIN = 0xF0

    _pgn_mask = 0x3FFFF

    _ps_mask = 0xff
    _ps_shift = 0

    _pf_mask = 0xff
    _pf_shift = 8

    _dp_mask = 0x1
    _dp_shift = 16

    _edp_mask = 0x1
    _edp_shift = 17

    def __init__(self, value: int):
        self.v = value

    def __gt__(self, rhs) -> bool:
        return self.v > rhs.v if isinstance(rhs, J1939PGN) else False

    def __eq__(self, rhs) -> bool:
        return self.v == rhs.v if isinstance(rhs, J1939PGN) else False

    def __lt__(self, rhs) -> bool:
        return self.v < rhs.v if isinstance(rhs, J1939PGN) else False

    def __int__(self):
        return self.v

    def to_bytes(self) -> bytes:
        return self.v.to_bytes(3, "little")

    @classmethod
    def from_comps(cls, edp: int, dp: int, pf: int, ps: int):
        return J1939PGN(
            (edp & J1939PGN._edp_mask) << J1939PGN._edp_shift |
            (dp & J1939PGN._dp_mask) << J1939PGN._dp_shift |
            (pf & J1939PGN._pf_mask) << J1939PGN._pf_shift |
            (ps & J1939PGN._ps_mask) << J1939PGN._ps_shift)

    @classmethod
    def from_bytes(cls, _bytes: Sequence[int]):
        return J1939PGN(int.from_bytes(_bytes[0:3], "little", signed=False) & J1939PGN._pgn_mask)

    def ps(self) -> int:
        return (self.v >> J1939PGN._ps_shift) & J1939PGN._ps_mask

    def pf(self) -> int:
        return (self.v >> J1939PGN._pf_shift) & J1939PGN._pf_mask

    def dp(self) -> int:
        return (self.v >> J1939PGN._dp_shift) & J1939PGN._dp_mask

    def edp(self) -> int:
        return (self.v >> J1939PGN._edp_shift) & J1939PGN._edp_mask

    def is_pdu1(self) -> bool:
        return self.pf() < self.J1939_PF_PDU2_MIN

    def is_valid(self) -> bool:
        return (self.v & (~0x3ffff)) == 0


class J1939StandardPGN(Enum):
    ACKNOWLEDGEMENT = J1939PGN(0x0E800)
    ADDRESS_CLAIMED = J1939PGN(0x0EE00)
    PGN_REQUEST = J1939PGN(0x0EA00)
    SOFTWARE_ID = J1939PGN(0x0FEDA)
    PROPRIETARY_A = J1939PGN(0x0EF00)
    PROPRIETARY_B = J1939PGN(0x0FF11)  # Can be in range of [0x0FF00, 0x0FFFF]
    PGN_MAX = J1939PGN(0x3FFFF)
    NO_NAME = J1939PGN(0)
    TP_CM = J1939PGN(0xEC00)
