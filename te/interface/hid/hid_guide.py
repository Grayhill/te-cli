from typing import Union, TYPE_CHECKING

from te.interface.common import ScreenID, Status, VariableID, VariableData
from te.interface.guide import GUIDEInterface
from te.interface.hid.hid_reports import BaseReport

if TYPE_CHECKING:
    from te.interface.hid import HIDTouchEncoder


class ScreenReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        self.screen_id: ScreenID = ScreenID(self.raw_report[1])


class VariableReport(ScreenReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        self.variable_id: VariableID = VariableID(self.raw_report[2])
        self.variable_size: int = int.from_bytes(self.raw_report[3:5], 'little')
        self.variable_val: VariableData = VariableData(self.raw_report[5:])


class GuideErrorReport(BaseReport):
    def __init__(self, raw_report: bytes):
        super().__init__(raw_report)
        if self.report_id != 0x20:
            raise ValueError('Invalid report ID')
        if len(self.raw_report) < 2:
            raise ValueError('Not valid data len')
        self.failed_report_id = self.raw_report[1]


class HIDGUIDEInterface(GUIDEInterface):
    def __init__(self, te: 'HIDTouchEncoder'):
        super().__init__(te)
        self.te: 'HIDTouchEncoder' = te

    def get_screen(self) -> Union[ScreenID, Status]:
        res = self.te.hid.get_input_report(self.Commands.SCREEN, 2)
        if not res:
            return Status.ERROR
        res = ScreenReport(res)
        # Output will be [SCREEN_REPORT, screen_id] if successful
        return res.screen_id

    def set_screen(self, screen_id: ScreenID | int) -> Status:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)

        self.te.send_widget_command([self.Commands.SCREEN, screen_id])
        res = self.te.await_res(expected_res=[GuideErrorReport, ScreenReport])
        if isinstance(res, GuideErrorReport) and res.failed_report_id == self.Commands.SCREEN:
            return Status.NACK
        if isinstance(res, ScreenReport) and res.screen_id == screen_id:
            return Status.SUCCESS
        return Status.ERROR

    def get_var(self, screen_id: ScreenID | int, var_id: VariableID | int) -> Union[VariableData, Status]:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)
        if isinstance(var_id, int):
            var_id = VariableID(var_id)

        written = self.te.send_widget_command([self.Commands.VARIABLE, screen_id, var_id, 0x00, 0x00])
        # The Second check is for Windows because `written` is self.te.MAX_REPORT_SIZE + len(cmd)
        if written != 5 and (written - self.te.MAX_REPORT_SIZE) != 5:
            return Status.ERROR
        try:
            report = self.te.hid.get_input_report(self.Commands.VARIABLE, self.te.MAX_REPORT_SIZE + written)
            res = VariableReport(report)
        except OSError or ValueError:
            return Status.ERROR
        return res.variable_val

    def set_var(self, screen_id: ScreenID | int, var_id: VariableID | int, var_data: VariableData) -> Status:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)
        if isinstance(var_id, int):
            var_id = VariableID(var_id)

        var_bytes = list(var_data.data)
        var_size_bytes = [b for b in len(var_bytes).to_bytes(2, 'little')]
        self.te.send_widget_command([self.Commands.VARIABLE, screen_id, var_id] + var_size_bytes + var_bytes)
        res = self.te.await_res(expected_res=[GuideErrorReport, VariableReport])
        if isinstance(res, GuideErrorReport) and res.failed_report_id == self.Commands.VARIABLE:
            return Status.NACK
        if isinstance(res, VariableReport) and res.screen_id == screen_id and res.variable_id == var_id:
            return Status.SUCCESS
        return Status.ERROR
