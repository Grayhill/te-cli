from enum import Enum

from te.interface.j1939.comm_interface.j1939_pgn import J1939PGN


class AckCode(Enum):
    OK = 0  # positive
    NACK = 1  # negative
    ACCESS_DENIED = 2  # access denied
    CANT_RESPOND = 3  # can't respond


class TePGN(Enum):
    COMMAND_DATA = J1939PGN(0x0FFEF)
    AUTHENTICATION = J1939PGN(0x13200)
    LIVE_UPDATE = J1939PGN(0x13300)
    AUX = J1939PGN(0x13100)
    GUIDE = J1939PGN(0x0FF11)
    RIE = J1939PGN(0x18FF0E)
    CALIBRATION = J1939PGN(0x0FF0F)
