import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Any, Protocol

from te.interface.common import ProjectInfo, Authentication, Version, Update, Status
from te.interface.guide import GUIDEInterface

log = logging.getLogger('TE')


class UpdateProgressCB(Protocol):
    def __call__(self, state: Enum, completed: Optional[int] = None, total: Optional[int] = None) -> None:
        pass


class TouchEncoder(ABC):
    """
    Touch Encoder Interface
    """
    RESTART_TIMEOUT = 20  # 20 seconds
    UPDATE_TIMEOUT = 60 * 12  # 12 minutes

    class Commands:
        ST_AUTH = 0x01
        RIE = 0x08
        RESTART = 0x44
        RESTART_UTILITY_APP = 0x45
        BRIGHTNESS = 0x80
        SUSPEND = 0xF0
        GET_VERSION_EXT = 0xC1
        GET_HARDWARE_ID = 0xC2
        GET_PROJECT_INFO = 0xC3
        LIVE_UPDATE = 0x55
        CONFIGURE_NAME = 0xE1

    def __init__(self):
        self.version: Version = Version()
        self.hardware_id: str = 'N/A'
        self.project_info: ProjectInfo = ProjectInfo()
        self.guide: Optional[GUIDEInterface] = None

    @property
    @abstractmethod
    def interface(self) -> str:
        """
        TODO: Rename this to avoid mixing HID and CAN terms (link layer vs network layer)
        Create interface identifier for the connected device
        :return: {interface}:{addr/sn}
        """
        raise NotImplementedError()

    @property
    def in_utility_app(self) -> bool:
        """
        Return True if the device is in Utility App, False otherwise.
        :return:
        """
        raise NotImplementedError()

    @abstractmethod
    def disconnect(self):
        """
        Disconnect a device from the underlying interface and clean up
        :return:
        """
        raise NotImplementedError()

    @abstractmethod
    def send_command(self, command: List[int]) -> int:
        """
        Sends a command to the device.
        :param command: Command and data
        :return:
        """
        raise NotImplementedError()

    @abstractmethod
    def await_res(self, expected_res: Any = None, timeout: float = 1.0, timestamp: Optional[float] = None) -> Any:
        """
        Await response from the device.
        :param timestamp: Get res after the specified timestamp
        :param timeout: Time to wait
        :param expected_res: If specified, wait for the specified type of res
        :type expected_res: List
        :return: Report/Msg if response, otherwise None
        """
        raise NotImplementedError()

    @abstractmethod
    def authenticate(self, clearance: Authentication.Clearance) -> Status:
        """
        Authenticate with the connected device for clearance level.
        :param clearance: Authentication.Clearance enum
        :return:
        """
        raise NotImplementedError()

    def refresh_version_info(self) -> Status:
        """
        Fetch the latest firmware version from the device.
        :return:
        """
        self.version = Version()
        return Status.SUCCESS

    def refresh_hardware_info(self) -> Status:
        """
        Fetch the hardware info from the device.
        :return:
        """
        self.hardware_id = 'Not Found'
        self.send_command([self.Commands.GET_HARDWARE_ID, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return Status.SUCCESS

    def refresh_project_info(self) -> Status:
        """
        Fetch the project info from the device.
        :return:
        """
        self.project_info = ProjectInfo()
        self.send_command([self.Commands.GET_PROJECT_INFO, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return Status.SUCCESS

    def refresh_info(self) -> Status:
        """
        Refresh the locally stored Touch Encoder information listed below:
        - Version
        - Hardware ID
        - Project Info
        :param: fetch_ext_ver: If True, fetch extended information from the Touch Encoder
        :param: authenticate: If True, authenticate with the device to refresh the ext version
        :return:
        """
        v_status = self.refresh_version_info() == Status.SUCCESS
        h_status = self.refresh_hardware_info() == Status.SUCCESS
        p_status = self.refresh_project_info() == Status.SUCCESS

        return Status.SUCCESS if (v_status and h_status and p_status) else Status.ERROR

    @abstractmethod
    def set_brightness(self, level: int, store: bool = False) -> Status:
        """
        Set the brightness of the device to the specified level
        :param level: New brightness level
        :param store:
        :return:
        """
        self.send_command([self.Commands.BRIGHTNESS, 0x00, (level & 0x7F) + (store << 7), 0x00, 0x00, 0x00, 0x00, 0x00])
        return Status.SUCCESS

    @abstractmethod
    def set_raw_input_event(self, enable: bool) -> Status:
        """
        Enable or disable the raw input event report on the device.
        :param enable:
        :return:
        """
        self.send_command([self.Commands.RIE, int(enable), 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return Status.SUCCESS

    @abstractmethod
    def restart(self, to_utility: bool = False, wait: bool = True, authenticate: bool = False) -> Status:
        """
        Restart the device.
        If to_utility is specified, a device will be restarted to utility app (Note: a device needs to be authenticated
        for the service tool prior to restart).
        :param to_utility: Restart in utility mode
        :param wait: Wait for the device to restart
        :param authenticate: If true, authenticate with the device when restarting to utility app
        :return:
        """
        # Restart TE, doesn't matter which variant it is
        if to_utility:
            if authenticate:
                status = self.authenticate(Authentication.Clearance.SERVICE_TOOL)
                if status != Status.SUCCESS:
                    return status
            self.send_command([self.Commands.RESTART_UTILITY_APP, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        else:
            self.send_command([self.Commands.RESTART, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

        return Status.SUCCESS

    @abstractmethod
    def update(self, filepath: str, progress_cb: UpdateProgressCB) -> Update.Status:
        """
        Update the connected device to the given package.
        :param progress_cb: Callback function for status updates, Callable[[Enum, int, int], None]
        :param filepath: Path to .tepkg
        :return: Update status
        """
        raise NotImplementedError()
