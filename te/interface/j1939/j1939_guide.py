from typing import Union, Optional, TYPE_CHECKING

from te.interface.common import ScreenID, Status, VariableID, VariableData
from te.interface.guide import GUIDEInterface
from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN
from te.interface.j1939.j1939_messages import SourceAddressMsg, _Address, AckMsg
from te.interface.j1939.j1939_te_statics import TePGN, AckCode

if TYPE_CHECKING:
    from te.interface.j1939 import J1939TouchEncoder


def guide_response(pgn: J1939PGN, command: int, screen_id: int = None, var_id: int = None):
    class GUIDEMsg(SourceAddressMsg):
        def __init__(self, address: _Address, data: bytes, source_address: int) -> None:
            super().__init__(address, data, source_address)

            if self.pgn != pgn:
                raise ValueError('Invalid screen PGN')
            if len(self.data) < 2:
                raise ValueError('Invalid data len')

            self.guide_cmd = self.data[0]
            if self.guide_cmd != command:
                raise ValueError('Invalid command')

            self.screen_id: ScreenID = ScreenID(self.data[1])

            if screen_id and self.screen_id != screen_id:
                raise ValueError('Invalid Screen ID')

            # if var_id is passed in, we are assuming the data should have a var_id
            if var_id and self.data[2] != var_id:
                raise ValueError("Invalid Var ID")

        @property
        def variable_id(self) -> Optional[VariableID]:
            if len(self.data) > 2:
                return VariableID(self.data[2])
            return None

        @property
        def variable_val(self) -> Optional[VariableData]:
            if len(self.data) > 2:
                return VariableData(self.data[3:])
            return None
    return GUIDEMsg


class J1939GUIDEInterface(GUIDEInterface):
    GUIDE_GET = 0x0A
    GUIDE_SET = 0x0B
    PGN_CONFIG = 0xD9

    def __init__(self, te: 'J1939TouchEncoder'):
        super().__init__(te)
        self.te: 'J1939TouchEncoder' = te
        self.response_pgn = TePGN.GUIDE.value

    def set_response_pgn(self, pgn: Optional[J1939PGN] = None) -> Status:
        """
        Set the GUIDE response PGN, accepted range is 0x00..0x3FFFF.
        Note: On the TE, PGN is set by (PGN_VAL & 0x3FFFF).
        :param pgn:
        :return:
        """
        if pgn:
            self.response_pgn = pgn
        self.te.send_command([self.PGN_CONFIG] + list(self.response_pgn.to_bytes()) + [0x00, 0x00, 0x00, 0x00])
        msg = self.te.await_res(expected_res=[AckMsg])
        if msg and msg.ack_code == AckCode.NACK:
            return Status.NACK
        elif msg and msg.ack_code == AckCode.OK and msg.group_func_val == self.PGN_CONFIG:
            return Status.SUCCESS
        return Status.ERROR

    def get_screen(self) -> Union[ScreenID, Status]:
        self.te.send_command([self.GUIDE_GET, self.Commands.SCREEN, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        msg = self.te.await_res(expected_res=[guide_response(self.response_pgn, command=self.Commands.SCREEN)])
        if msg:
            return msg.screen_id
        return Status.ERROR

    def set_screen(self, screen_id: ScreenID | int) -> Status:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)

        self.te.send_command([self.GUIDE_SET, self.Commands.SCREEN, screen_id, 0x00, 0x00, 0x00, 0x00, 0x00])
        screen_msg = guide_response(self.response_pgn, command=self.Commands.SCREEN, screen_id=int(screen_id))
        msg = self.te.await_res(expected_res=[screen_msg, AckMsg])
        if isinstance(msg, AckMsg) and msg.ack_code == AckCode.NACK:
            return Status.NACK
        if isinstance(msg, screen_msg):
            return Status.SUCCESS
        return Status.ERROR

    def get_var(self, screen_id: ScreenID | int, var_id: VariableID | int) -> Union[VariableData, Status]:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)
        if isinstance(var_id, int):
            var_id = VariableID(var_id)

        self.te.send_command([self.GUIDE_GET, self.Commands.VARIABLE, screen_id, var_id,
                              0x00, 0x00, 0x00, 0x00])
        msg = self.te.await_res(expected_res=[guide_response(self.response_pgn, command=self.Commands.VARIABLE,
                                                             screen_id=int(screen_id), var_id=int(var_id))])
        if msg:
            return msg.variable_val
        return Status.ERROR

    def set_var(self, screen_id: ScreenID | int, var_id: VariableID | int, var_data: VariableData) -> Status:
        if isinstance(screen_id, int):
            screen_id = ScreenID(screen_id)
        if isinstance(var_id, int):
            var_id = VariableID(var_id)

        self.te.send_command([self.GUIDE_SET, self.Commands.VARIABLE, screen_id, var_id] +
                             list(var_data.data))
        int_var_msg = guide_response(self.response_pgn, command=self.Commands.INT_VARIABLE,
                                     screen_id=int(screen_id), var_id=int(var_id))
        str_var_msg = guide_response(self.response_pgn, command=self.Commands.STRING_VARIABLE,
                                     screen_id=int(screen_id), var_id=int(var_id))
        msg = self.te.await_res(expected_res=[int_var_msg, str_var_msg, AckMsg])

        print(msg)
        if isinstance(msg, AckMsg) and msg.ack_code == AckCode.NACK:
            return Status.NACK
        if ((isinstance(msg, int_var_msg) or isinstance(msg, str_var_msg))
                and msg.screen_id == screen_id and msg.variable_id == var_id):
            return Status.SUCCESS
        return Status.ERROR
