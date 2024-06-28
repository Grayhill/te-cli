from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Union
from te.interface.common import Status, ScreenID, VariableID, VariableData

if TYPE_CHECKING:
    from te.interface import TouchEncoder


class GuideNotifications:
    INT_VAR = 3
    STRING_VAR = 4
    KNOB_EVENT = 16
    TOUCH_EVENT = 17
    GESTURE_EVENT = 18
    SCENE_EVENT = 19


class GuideTouchType(Enum):
    DOWN = 0
    MOVE = 1
    UP = 2
    ENTER = 3
    LEAVE = 4


class GuideGestureType(Enum):
    TAP = 0
    AXIS_SWIPE = 1


class GuideGestureDirection(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    UNKNOWN = 4


class GUIDEInterface(ABC):
    class Commands:
        SCREEN = 0x01
        VARIABLE = 0x02
        INT_VARIABLE = 0x03
        STRING_VARIABLE = 0x04

    def __init__(self, te: 'TouchEncoder'):
        self.te: 'TouchEncoder' = te

    @abstractmethod
    def get_screen(self) -> Union[ScreenID, Status]:
        """
        Send a Screen GET request and retrieve the ID of the currently active screen on the device.
        :return: Screen ID of the active screen
        """
        raise NotImplementedError()

    @abstractmethod
    def set_screen(self, screen_id: ScreenID | int) -> Status:
        """
        Set the screen on the device to the given screen ID.
        :param screen_id: Screen ID to set
        :return: Status
        """
        raise NotImplementedError()

    @abstractmethod
    def get_var(self, screen_id: ScreenID | int, var_id: VariableID | int) -> Union[VariableData, Status]:
        """
        Get the value of a variable from the specified screen ID on the device
        :param screen_id: Screen ID where the variable is located
        :param var_id: Variable ID to retrieve
        :return: Variable value
        """
        raise NotImplementedError()

    @abstractmethod
    def set_var(self, screen_id: ScreenID | int, var_id: VariableID | int, var_data: VariableData) -> Status:
        """
        Set the value of a variable from the specified screen ID on the device
        :param screen_id: Screen ID where the variable is located
        :param var_id: Variable ID to set
        :param var_data: the Value of the variable
        :return: Status
        """
        raise NotImplementedError()
