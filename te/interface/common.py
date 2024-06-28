import os
from dataclasses import dataclass
from enum import Enum, auto

from typing import Any, Union


class Status(Enum):
    SUCCESS = 'Success'
    NACK = 'NACK'
    ACCESS_DENIED = 'Access Denied'
    AUTH_REQUIRED = 'Auth Required'
    AUTH_REQUEST_FAILED = 'Auth Request Failed'
    AUTH_CHALLENGE_FAILED = 'Auth Challenge Failed'
    RESTART_TIMEOUT = 'Restart Timed Out'
    ERROR = 'Error'


class ProjectType(Enum):
    UNKNOWN = -1
    GUIDE = 0
    GIIB = 1


@dataclass
class Version:
    firmware: str = 'Not Found'
    bootloader: str = 'Not Found'
    project: str = 'Not Found'
    custom_module: str = 'Not Found'

    @staticmethod
    def parse_version_str(ver_str):
        data_split = ver_str.split('\n')
        to_return = {}
        name_map = {'FW': 'firmware', 'BL': 'bootloader', 'PJ': 'project', 'CM': 'custom_module'}
        for d in data_split:
            d_split = d.split(':')
            to_return[name_map[d_split[0]]] = d_split[1]
        return to_return


class HardwareID(Enum):
    BAD = -1
    TE_RF_USB = 0x00  # Touch Encoder Refresh USB
    TE_RF_CAN = 0x01  # Touch Encoder Refresh CAN
    TE_FX_USB = 0x10  # Touch Encoder Flush Mount USB
    TE_FX_CAN = 0x11  # Touch Encoder Flush Mount CAN
    TE_MX = 0x100  # Touch Encoder Mix (USB + CAN)


class ProjectInfo:
    def __init__(self, p_type: ProjectType = ProjectType.UNKNOWN, checksum: int = -1):
        self.type: ProjectType = ProjectType(p_type)
        self.checksum = checksum

    @classmethod
    def from_bytes(cls, _bytes: bytes):
        return ProjectInfo(ProjectType(_bytes[0]), int.from_bytes(_bytes[1:5], 'little', signed=False))

    def __str__(self):
        return f'{self.type.name} {self.checksum}'


class Authentication:
    class Clearance(Enum):
        INVALID = 255
        SERVICE_TOOL = 1

    class State(Enum):
        COMPLETE = 255
        CHALLENGE = 0
        RESPONSE = 1

    @staticmethod
    def service_tool_secret(secret: int, magic: int) -> int:
        return (magic ^ (secret + 0x63f07b35 + (magic << 6) + (magic >> 2))) & 0xffffffff

    @classmethod
    def secret(cls, clr: Clearance, secret: int, magic: int) -> int:
        if clr == cls.Clearance.SERVICE_TOOL:
            return cls.service_tool_secret(secret, magic)
        else:
            return magic


class Update:
    class State(Enum):
        ERROR = auto()
        UPDATE_REQUEST = auto()
        UPDATE_CONFIRMATION = auto()
        UPDATE_REJECTED = auto()
        DEVICE_BUSY = auto()
        FILE_UPLOAD = auto()
        UPLOAD_ERROR = auto()
        UPDATING = auto()
        UPDATING_BOOTLOADER = auto()
        UPDATING_FIRMWARE = auto()
        UPDATING_PROJECT = auto()
        SUCCESS = auto()
        REBOOTING = auto()

        @classmethod
        def from_component_type(cls, comp_type: Enum):
            match comp_type:
                case Update.ComponentType.BOOTLOADER:
                    return cls.UPDATING_BOOTLOADER
                case Update.ComponentType.FIRMWARE:
                    return cls.UPDATING_FIRMWARE
                case Update.ComponentType.PROJECT:
                    return cls.UPDATING_PROJECT
                case _:
                    return cls.UPDATING

    class ComponentType(Enum):
        UNKNOWN = -1
        PACKAGE = 0
        BOOTLOADER = 1
        FIRMWARE = 2
        PROJECT = 3

        @classmethod
        def from_filename(cls, filename: str):
            _, ext = os.path.splitext(filename)
            if ext:
                match ext:
                    case '.zip':
                        return Update.ComponentType.PROJECT
                    case '.tepkg':
                        return Update.ComponentType.PACKAGE
            return Update.ComponentType.UNKNOWN

    class ComponentStatus(Enum):
        UNKNOWN = -1
        BUSY = 0xB1
        PROGRESS = 0x30
        END = 0xF1

    class Status(Enum):
        FAILURE = -2
        ERROR = -1
        ONGOING = 0
        SUCCESS = 1
        SUCCESS_RESTART = 2
        SUCCESS_UPTODATE = 3
        TIMEOUT = 4

    class StatusType(Enum):
        UPLOAD = 1
        UPDATE = 2
        COMPONENT = 3

    class UploadError(Enum):
        OK = 0
        UNKNOWN = 1
        TIMEOUT = 2
        OVERFLOW = 3
        IO_ERROR = 4


class ScreenID(int):
    def __new__(cls, x: Any):
        v = super().__new__(cls, x)
        if v < 0:
            raise ValueError('Invalid screen ID')
        return v


class VariableID(int):
    def __new__(cls, x: Any):
        v = super().__new__(cls, x)
        if v < 0:
            raise ValueError('Invalid variable ID')
        return v


class VariableData:
    def __init__(self, value: Union[bytes, int, str, list]):
        if isinstance(value, int):
            self.data = value.to_bytes(4, 'little', signed=True)
        elif isinstance(value, str):
            self.data = bytes(value, 'utf-8') + b'\x00'
        elif isinstance(value, list):
            self.data = bytes(value)
        else:
            self.data = value

    def to_int(self) -> int:
        if len(self.data) > 4:
            raise ValueError()
        return int.from_bytes(self.data, byteorder='little', signed=True)

    def to_string(self) -> str:
        value = str(self.data, 'utf-8')
        if value.endswith('\x00'):
            value = value.removesuffix('\x00')
        return value
