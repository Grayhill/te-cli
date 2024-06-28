import re
from typing import TypeAlias, Any

from te.interface.common import Authentication, HardwareID, Update, Version, ScreenID, VariableID
from te.interface.guide import GuideNotifications, GuideTouchType, GuideGestureType, GuideGestureDirection
from te.interface.j1939.comm_interface import Message, J1939StandardPGN, J1939Name
from te.interface.j1939.j1939_te_statics import TePGN, AckCode
from te.interface import TouchEncoder

_Address: TypeAlias = tuple[Any, ...]


class SourceAddressMsg(Message):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data)

        if self.sa != source_address:
            raise ValueError('Invalid source address')


class AddressClaimMsg(Message):
    def __init__(self, address: _Address, data: bytes, source_address: int = -1) -> None:
        # TODO: Refactor the messages to remove source_address from init
        super().__init__(address, data)

        if self.pgn != J1939StandardPGN.ADDRESS_CLAIMED.value:
            raise ValueError('Invalid address claimed PGN')
        self.j1939_name: J1939Name = J1939Name(int.from_bytes(self.data[:8], 'little', signed=False))


class AckMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != J1939StandardPGN.ACKNOWLEDGEMENT.value:
            raise ValueError('Invalid ack PGN')
        if self.length != 8:
            raise ValueError('Invalid data length')

        self.ack_code: AckCode = AckCode(self.data[0])
        self.ack_pgn: int = int.from_bytes(self.data[0:3], "little", signed=False) & int(J1939StandardPGN.PGN_MAX.value)
        self.group_func_val = self.data[1]


class RestartAckMsg(AckMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)
        if self.group_func_val != TouchEncoder.Commands.RESTART:
            raise ValueError('Invalid restart ack msg')


class SoftwareIDMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != J1939StandardPGN.SOFTWARE_ID.value:
            raise ValueError('Invalid PGN')

    @property
    def version(self) -> Version:
        data = self.data.decode('ascii')
        match = re.search(r'F:(?P<firmware>\d+.\d+.\d+)\*'
                          r'B:(?P<bootloader>\d+.\d+.\d+)\*'
                          r'(P:(?P<project>\d+.\d+.\d+)\*)?', data)
        if match:
            return Version(**match.groupdict())
        return Version()


class VersionMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != TePGN.AUX.value:
            raise ValueError('Invalid PGN')

    @property
    def version(self) -> Version:
        ver_str = self.data.decode()[:-1]
        return Version(**Version.parse_version_str(ver_str))


class CommandMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != TePGN.COMMAND_DATA.value:
            raise ValueError('Invalid PGN')

        self.command: int = self.data[0]


class HardwareIDMsg(CommandMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.command != TouchEncoder.Commands.GET_HARDWARE_ID:
            raise ValueError('Invalid hardware ID command')

        self.hardware_id: HardwareID = HardwareID(int.from_bytes(self.data[1:], 'little'))


class ProjectInfoMsg(CommandMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.command != TouchEncoder.Commands.GET_PROJECT_INFO:
            raise ValueError('Invalid project info command')

        self.project_info: bytes = self.data[1:]


class AuthMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != TePGN.AUTHENTICATION.value:
            raise ValueError('Invalid auth PGN')

        self.auth_state: Authentication.State = Authentication.State(self.data[0])
        self.challenge: int = int.from_bytes(self.data[1:5], 'little')


class UpdateAckMsg(AckMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)
        if self.data[1] != TouchEncoder.Commands.LIVE_UPDATE:
            raise ValueError('Invalid update ack msg')

        self.status: int = self.data[0]


class UpdateStatusMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int, session_pgn: int) -> None:
        super().__init__(address, data, source_address)
        if self.pgn != session_pgn:
            raise ValueError('Invalid session PGN')

        self.status_type: Update.StatusType = Update.StatusType(self.data[0])
        match self.status_type:
            case Update.StatusType.UPLOAD:
                if len(self.data) != 2:
                    raise ValueError('Invalid data len')
            case Update.StatusType.UPDATE:
                if len(self.data) < 2:
                    raise ValueError('Invalid data len')
            case Update.StatusType.COMPONENT:
                if len(self.data) < 7:
                    raise ValueError('Invalid data len')
            case _:
                raise ValueError('Invalid status type')

        self.err: Update.UploadError = Update.UploadError(int.from_bytes(self.data[1:2], 'little'))
        self.update_status: Update.Status = Update.Status(int.from_bytes(self.data[1:2], 'little', signed=True))

    @property
    def component_type(self) -> Update.ComponentType:
        if self.status_type != Update.StatusType.COMPONENT:
            return Update.ComponentType.UNKNOWN
        return Update.ComponentType(self.data[1])

    @property
    def component_status(self) -> Update.ComponentStatus:
        if self.status_type != Update.StatusType.COMPONENT:
            return Update.ComponentStatus.UNKNOWN
        return Update.ComponentStatus(self.data[2])

    @property
    def component_progress(self) -> int:
        if self.status_type != Update.StatusType.COMPONENT:
            return 0
        return int.from_bytes(self.data[3:7], 'little')


class CalibrationMsg(SourceAddressMsg):
    """
    Raw calibration message format:
    Ex: 18FF0F60 4C 7B FF FF 19 FF FF FF
    Breakdown:
    - 18FF0F60: Address
    - 4C 7B -> 7B 4C: Raw Angle
    - 19: Position

    Calibrated message format:
    Ex: 18FF0FF2 01 4C CD 00 00 FF FF FF
    Breakdown:
    - 18FF0FF2: Address
    - 01: Position
    - 4C CD -> CD 4C: Raw Angle
    """
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != TePGN.CALIBRATION.value:
            raise ValueError('Invalid calibration PGN')

        if data[2] == 0xFF and data[3] == 0xFF:
            self.raw_calibration_msg = True
            self.position = int(self.data[4])
            self.raw_angle = int.from_bytes(self.data[:2], byteorder='little')
        else:
            self.raw_calibration_msg = False
            self.position = int(self.data[0])
            self.raw_angle = int.from_bytes(self.data[1:3], byteorder='little')

        self.angle = round((self.raw_angle * 360) / 65536.0, 2)


class GuideMsg(SourceAddressMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.pgn != TePGN.GUIDE.value:
            raise ValueError('Invalid guide PGN')


class GuideIntVarMsg(GuideMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.data[0] != GuideNotifications.INT_VAR:
            raise ValueError('Invalid guide event')

        self.screen_id: ScreenID = ScreenID(self.data[1])
        self.variable_id: VariableID = VariableID(self.data[2])
        self.value: int = int.from_bytes(self.data[3:7], 'little')


class GuideStringVarMsg(GuideMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.data[0] != GuideNotifications.STRING_VAR:
            raise ValueError('Invalid guide event')

        self.screen_id: ScreenID = ScreenID(self.data[1])
        self.variable_id: VariableID = VariableID(self.data[2])
        self.value: str = self.data[3:].decode('utf-8')


class GuideKnobEventMsg(GuideMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.data[0] != GuideNotifications.KNOB_EVENT:
            raise ValueError('Invalid guide event')

        self.element_id: int = self.data[1]
        self.relative_value: int = int.from_bytes(self.data[3:5], 'little', signed=True)


class GuideTouchEventMsg(GuideMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.data[0] != GuideNotifications.TOUCH_EVENT:
            raise ValueError('Invalid guide event')

        self.element_id: int = self.data[1]
        self.touch_type: GuideTouchType = GuideTouchType(self.data[2])
        self.x: int = int.from_bytes(self.data[4:6], 'little', signed=True)
        self.y: int = int.from_bytes(self.data[6:8], 'little', signed=True)


class GuideGestureEventMsg(GuideMsg):
    def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
        super().__init__(address, data, source_address)

        if self.data[0] != GuideNotifications.GESTURE_EVENT:
            raise ValueError('Invalid guide event')

        self.element_id: int = self.data[1]
        self.gesture_type: GuideGestureType = GuideGestureType(self.data[2])

        self.x: int = 0
        self.y: int = 0
        self.direction: GuideGestureDirection.UNKNOWN

        if self.gesture_type == GuideGestureType.TAP:
            self.x = int.from_bytes(self.data[3:5], 'little', signed=True)
            self.y = int.from_bytes(self.data[5:7], 'little', signed=True)
        else:
            self.direction = GuideGestureDirection(self.data[3])
