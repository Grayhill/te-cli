from collections.abc import Iterable
from enum import Enum
from typing import Optional

from te.interface import TouchEncoder
from te.interface.common import Authentication, HardwareID, ProjectInfo, Update, ScreenID, VariableID
from te.interface.guide import GuideNotifications, GuideGestureType, GuideGestureDirection, GuideTouchType
from te.interface.hid.hid_te_statics import ContextIDs


class ReportIDs:
    GIIBEVT = 1
    GIIBRPT = 3
    CS_DATA_LONG = 3
    CS_DATA_SHORT = 4
    COMMAND_ACK = 5
    UPDATE_DATA = 8
    UPDATE_STATUS = 9
    BL_VER = 16
    FW_VER = 17
    PROJ_VER = 18
    CMOD_VER = 19


class AckReportCode(Enum):
    OK = 1
    UNKNOWN = 0
    ERR = -1
    ACC_DENIED = -2


class BaseReport:
    def __init__(self, raw_report: bytes, timestamp: Optional[float] = None):
        self.timestamp = timestamp
        if len(raw_report) == 0:
            raise ValueError('No report to parse')

        self.raw_report = raw_report
        self.report_id = raw_report[0]

    def __str__(self) -> str:
        return self.raw_report.hex()


class ContextSensitiveReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        self.context_id = raw_report[1]

        if self.report_id == ReportIDs.CS_DATA_SHORT:
            self.size = raw_report[2]
            self.data = bytes(raw_report[3:self.size + 3])
        elif self.report_id == ReportIDs.CS_DATA_LONG:
            self.size = int.from_bytes(raw_report[2:4], 'little')
            self.data = bytes(raw_report[4:self.size + 4])
        else:
            raise ValueError('Non CS Data report ID')

    @classmethod
    def from_fragments(cls, context_id: int, *fragments: bytes | int | Iterable[int]) -> 'ContextSensitiveReport':
        report = bytearray(4)
        for f in fragments:
            if isinstance(f, bytes):
                report += f
            elif isinstance(f, Iterable):
                report.extend(f)
            elif isinstance(f, int):
                report.append(f)
            else:
                raise ValueError()

        sz = len(report) - 4
        if sz <= 61:
            report[1] = ReportIDs.CS_DATA_SHORT
            report[2] = context_id
            report[3] = sz
            return ContextSensitiveReport(report[1:])
        elif sz <= 1020:
            report[0] = ReportIDs.CS_DATA_LONG
            report[1] = context_id
            report[2:4] = sz.to_bytes(2, 'little')
            return ContextSensitiveReport(report)
        else:
            raise ValueError("Data too big for cs data report")


class AckReport(BaseReport):
    """
    Ack report output for HID Touch Encoders.
    """
    LENGTH = 11

    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if len(raw_report) < self.LENGTH:
            raise ValueError('Incorrect length')

        self.command = raw_report[1]
        # TODO: Seems like this is only reading one byte. Change and test to verify it does not break
        self.code = AckReportCode(int.from_bytes(raw_report[2:3], 'little', signed=True))
        self.data = raw_report[3:]

        if self.report_id != ReportIDs.COMMAND_ACK:
            raise ValueError('Incorrect report ID')


class HardwareIDReport(AckReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        if self.command != TouchEncoder.Commands.GET_HARDWARE_ID:
            raise ValueError('Incorrect hardware ID command')

        self.hardware_id: HardwareID = HardwareID(int.from_bytes(self.data[:4], 'little'))


class ProjectInfoReport(AckReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        if self.command != TouchEncoder.Commands.GET_PROJECT_INFO:
            raise ValueError('Incorrect project info command')

        self.project_info: ProjectInfo = ProjectInfo.from_bytes(self.data[:5])


class AuthReport(ContextSensitiveReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.context_id != ContextIDs.AUTH:
            raise ValueError('Incorrect context ID')

        self.auth_state: Authentication.State = Authentication.State(raw_report[3])
        self.challenge = int.from_bytes(raw_report[4:8], 'little')


class UpdateAckMsg(AckReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        if self.command != TouchEncoder.Commands.LIVE_UPDATE:
            raise ValueError('Invalid update ack msg')

        self.status: int = self.raw_report[2]


class UpdateStatusMsg(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        self.status_type: Update.StatusType = Update.StatusType(self.raw_report[1])

        if self.report_id != ReportIDs.UPDATE_STATUS:
            raise ValueError('Invalid update status report')

        match self.status_type:
            case Update.StatusType.UPLOAD:
                if len(self.raw_report) < 3:
                    raise ValueError('Invalid data len')
            case Update.StatusType.UPDATE:
                if len(self.raw_report) < 3:
                    raise ValueError('Invalid data len')
            case Update.StatusType.COMPONENT:
                if len(self.raw_report) < 8:
                    raise ValueError('Invalid data len')
            case _:
                raise ValueError('Invalid status type')

        self.err: Update.UploadError = Update.UploadError(int.from_bytes(raw_report[2:3], 'little'))
        self.update_status: Update.Status = Update.Status(int.from_bytes(raw_report[2:3], 'little', signed=True))

    @property
    def component_type(self) -> Update.ComponentType:
        return Update.ComponentType(self.raw_report[2])

    @property
    def component_status(self) -> Update.ComponentStatus:
        return Update.ComponentStatus(self.raw_report[3])

    @property
    def component_progress(self) -> int:
        if len(self.raw_report) < 8:
            return 0
        return int.from_bytes(self.raw_report[4:8], 'little')


class CalibrationReport(AckReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.command != TouchEncoder.Commands.START_CALIB:
            raise ValueError('Invalid calibration command')
        if self.code != AckReportCode.OK:
            raise ValueError('Invalid ack code')

        if self.data[0] == 0xFF:
            self.raw_calibration_msg = True
            self.position = int(self.data[5])
        else:
            self.raw_calibration_msg = False
            self.position = int(self.data[0])

        self.raw_angle = int.from_bytes(self.data[1:3], byteorder='little')
        self.angle = round((self.raw_angle * 360) / 65536.0, 2)


class GuideIntVarReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.report_id != GuideNotifications.INT_VAR:
            raise ValueError('Incorrect report ID')

        self.screen_id: ScreenID = ScreenID(self.raw_report[1])
        self.screen_id: VariableID = VariableID(self.raw_report[2])
        self.value: int = int.from_bytes(self.raw_report[3:7], 'little')


class GuideStringVarReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.report_id != GuideNotifications.STRING_VAR:
            raise ValueError('Incorrect report ID')

        self.screen_id: ScreenID = ScreenID(self.raw_report[1])
        self.screen_id: VariableID = VariableID(self.raw_report[2])
        self.value: str = self.raw_report[3:].decode('utf-8')


class GuideKnobEventReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.report_id != GuideNotifications.KNOB_EVENT:
            raise ValueError('Incorrect report ID')

        self.element_id: int = self.raw_report[1]
        self.relative_value: int = int.from_bytes(self.raw_report[3:5], 'little', signed=True)


class GuideTouchEventReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.report_id != GuideNotifications.TOUCH_EVENT:
            raise ValueError('Incorrect report ID')

        self.element_id: int = self.raw_report[1]
        self.touch_type: GuideTouchType = GuideTouchType(self.raw_report[2])
        self.x: int = int.from_bytes(self.raw_report[4:6], 'little', signed=True)
        self.y: int = int.from_bytes(self.raw_report[6:8], 'little', signed=True)


class GuideGestureEventReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)

        if self.report_id != GuideNotifications.GESTURE_EVENT:
            raise ValueError('Incorrect report ID')

        self.element_id: int = self.raw_report[1]
        self.gesture_type: GuideGestureType = GuideGestureType(self.raw_report[2])

        self.x: int = 0
        self.y: int = 0
        self.direction: GuideGestureDirection.UNKNOWN

        if self.gesture_type == GuideGestureType.TAP:
            self.x = int.from_bytes(self.raw_report[4:6], 'little', signed=True)
            self.y = int.from_bytes(self.raw_report[6:8], 'little', signed=True)
        else:
            self.direction = GuideGestureDirection(self.raw_report[4])
