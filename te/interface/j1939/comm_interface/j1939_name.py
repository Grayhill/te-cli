from typing import Sequence


class J1939Name:
    _in_mask = 0x1FFFFF
    _in_shift = 0

    _mc_mask = 0x7FF
    _mc_shift = 21

    _ecu_inst_mask = 0x7
    _ecu_inst_shift = 32

    _fn_inst_mask = 0x1F
    _fn_inst_shift = 35

    _fn_mask = 0xFF
    _fn_shift = 40

    _vs_mask = 0x7F
    _vs_shift = 49

    _vs_inst_mask = 0xF
    _vs_inst_shift = 56

    _ig_mask = 0x7
    _ig_shift = 60

    _aac_mask = 0x1
    _aac_shift = 63

    # def __init__(self, value: int = socket.J1939_NO_NAME):
    def __init__(self, value):
        self.v = value

    def __gt__(self, rhs) -> bool:
        return self.v > rhs.v if isinstance(rhs, J1939Name) else False

    def __eq__(self, rhs) -> bool:
        return self.v == rhs.v if isinstance(rhs, J1939Name) else False

    def __lt__(self, rhs) -> bool:
        return self.v < rhs.v if isinstance(rhs, J1939Name) else False

    def __int__(self) -> int:
        return self.v

    def __hash__(self) -> int:
        return self.v

    def to_bytes(self) -> bytes:
        return self.v.to_bytes(8, "little")

    @classmethod
    def from_bytes(cls, bytes: Sequence[int]):
        return J1939Name(int.from_bytes(bytes[0:8], "little", signed=False))

    @classmethod
    def from_int(cls, value: int):
        return J1939Name(value)

    @classmethod
    def from_comps(cls, inum: int, mc: int, ecu_inst: int, fn_inst: int, fn: int, vs: int, vs_inst: int, ig: int,
                   aac: int):
        return J1939Name(
            ((inum & J1939Name._in_mask) << J1939Name._in_shift) |
            ((mc & J1939Name._mc_mask) << J1939Name._mc_shift) |
            ((ecu_inst & J1939Name._ecu_inst_mask) << J1939Name._ecu_inst_shift) |
            ((fn_inst & J1939Name._fn_inst_mask) << J1939Name._fn_inst_shift) |
            ((fn & J1939Name._fn_mask) << J1939Name._fn_shift) |
            ((vs & J1939Name._vs_mask) << J1939Name._vs_shift) |
            ((vs_inst & J1939Name._vs_inst_mask) << J1939Name._vs_inst_shift) |
            ((ig & J1939Name._ig_mask) << J1939Name._ig_shift) |
            ((aac & J1939Name._aac_mask) << J1939Name._aac_shift))

    def identity_number(self):
        return (self.v >> J1939Name._in_shift) & J1939Name._in_mask

    def manufacturer_code(self):
        return (self.v >> J1939Name._mc_shift) & J1939Name._mc_mask

    def ecu_instance(self):
        return (self.v >> J1939Name._ecu_inst_shift) & J1939Name._ecu_inst_mask

    def function_instance(self):
        return (self.v >> J1939Name._fn_inst_shift) & J1939Name._fn_inst_mask

    def function(self):
        return (self.v >> J1939Name._fn_shift) & J1939Name._fn_mask

    def vehicle_system(self):
        return (self.v >> J1939Name._vs_shift) & J1939Name._vs_mask

    def vehicle_system_instance(self):
        return (self.v >> J1939Name._vs_inst_shift) & J1939Name._vs_inst_mask

    def industry_group(self):
        return (self.v >> J1939Name._ig_shift) & J1939Name._ig_mask

    def arbitrary_address_capable(self):
        return (self.v >> J1939Name._aac_shift) & J1939Name._aac_mask
