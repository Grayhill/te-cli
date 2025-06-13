import ctypes
import logging
import platform
import threading
import time
from contextlib import contextmanager
from typing import Dict, Optional, List, Callable, TypeAlias

import hid as hidapi
import libusb

from te.interface.hid.comm_interface import HIDInterface, HIDInterfaceWin
from te.interface.hid.comm_interface.hid_device_descriptor import DeviceDescriptor
from te.interface.hid.hid_te_statics import VENDOR_ID, PRODUCT_ID

log = logging.getLogger('HIDManager')


HIDDevCallback: TypeAlias = Callable[[str], None]


class UserContext(ctypes.Structure):
    _fields_ = [
        ("new_devs", ctypes.py_object),
        ("removed_devs", ctypes.py_object)
    ]


@libusb.hotplug_callback_fn
def _hotplug_event_callback(_, dev: libusb.device, event, user_data) -> int:
    ctx = ctypes.cast(user_data, ctypes.POINTER(UserContext)).contents
    if event == libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED:
        ctx.new_devs.append(dev)
    elif event == libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT:
        ctx.removed_devs.append(dev)
    return 0


def hid_enum_devices() -> Dict[str, List[DeviceDescriptor]]:
    """
    Enumerate all HID devices.
    """
    sn_map = {}
    for i_face in hidapi.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        sn = i_face['serial_number']
        if not sn:
            continue
        if sn not in sn_map:
            sn_map[sn] = []
        sn_map[sn].append(DeviceDescriptor(
            path=i_face['path'],
            vendor_id=i_face['vendor_id'],
            product_id=i_face['product_id'],
            serial_number=sn,
            interface_number=i_face['interface_number']
        ))
    return sn_map


def hid_enum_dev_by_sn(serial_number: str) -> List[DeviceDescriptor]:
    """
    Enumerate all HID devices by serial number.
    """
    device_map = hid_enum_devices()
    return device_map.get(serial_number, [])


class HIDManager:
    def __init__(self):
        self.interfaces: Dict[str, HIDInterface] = {}

        # Libusb
        self._libusb_devs: Dict[int, str] = {}
        self._user_context = UserContext([], [])
        self._callback_handle = libusb.hotplug_callback_handle()
        self._lib_context = ctypes.POINTER(libusb.context)()
        res = libusb.init(ctypes.byref(self._lib_context))
        if res < 0:
            raise RuntimeError('Failed to initialize libusb context')

        # Hotplug event listener thread
        self._event_thread = None
        self.event_thread_running = False

        # Callbacks for new devices
        self._new_dev_callbacks: List[HIDDevCallback] = []
        self._dev_removed_callbacks: List[HIDDevCallback] = []

    def _add_device(self, dev_address: int, descriptors: List[DeviceDescriptor]):
        if not descriptors:
            log.warning(f'Failed to get device descriptor for dev address {dev_address}')
            return
        sn = descriptors[0].serial_number
        # Add to internal dev tracking
        self._libusb_devs[dev_address] = sn
        # Add to interface tracking
        if platform.system() == 'Windows':
            h_iface = HIDInterfaceWin(descriptors)
        else:
            h_iface = HIDInterface(descriptors)
        self.interfaces[sn] = h_iface

        for callback in self._new_dev_callbacks:
            th = threading.Thread(target=callback, args=(sn,))
            th.start()

    def _remove_device(self, dev_address: int):
        # Remove from internal dev tracking
        if dev_address not in self._libusb_devs:
            return
        sn = self._libusb_devs[dev_address]
        del self._libusb_devs[dev_address]

        # Remove from interface tracking
        if sn not in self.interfaces:
            return
        self.interfaces[sn].disconnect()
        del self.interfaces[sn]

        for callback in self._dev_removed_callbacks:
            th = threading.Thread(target=callback, args=(sn,))
            th.start()

    def register_new_dev_callback(self, callback: HIDDevCallback):
        """
        Register a callback to be called when a new device is detected.
        :param callback:
        :return:
        """
        self._new_dev_callbacks.append(callback)

    def unregister_new_dev_callback(self, callback: HIDDevCallback):
        """
        Unregister a previously registered new device callback.
        :param callback:
        :return:
        """
        self._new_dev_callbacks.remove(callback)

    def register_dev_removed_callback(self, callback: HIDDevCallback):
        """
        Register a callback to be called when a device is removed.
        :param callback:
        :return:
        """
        self._dev_removed_callbacks.append(callback)

    def unregister_dev_removed_callback(self, callback: HIDDevCallback):
        """
        Unregister a previously registered device removed callback.
        :param callback:
        :return:
        """
        self._dev_removed_callbacks.remove(callback)

    def scan_for_interfaces(self):
        """
        Scan for all HID interfaces and add them to the internal tracking.
        Note: Make sure to reinitialize any devices that were connected to any removed interfaces.
        :return:
        """
        # Disconnect all interfaces
        for iface in self.interfaces.values():
            iface.disconnect()
        self.interfaces = {}

        device_list_p = ctypes.POINTER(ctypes.POINTER(libusb.device))()
        res = libusb.get_device_list(self._lib_context, ctypes.byref(device_list_p))
        if res < libusb.LIBUSB_SUCCESS:
            log.error('Failed to get device list')
            return

        for i in range(res):
            dev = device_list_p[i]
            descriptors = self._get_device_descriptor(dev)
            if not descriptors or (descriptors[0].vendor_id != VENDOR_ID and descriptors[0].product_id != PRODUCT_ID):
                continue
            dev_address = libusb.get_device_address(dev)
            self._add_device(dev_address, descriptors)

    @contextmanager
    def hotplug_event_listener(self):
        """
        Context manager for starting and stopping the hotplug event listener.
        """
        self.start_hotplug_event_listener()
        try:
            yield
        finally:
            self.stop_hotplug_event_listener()

    def start_hotplug_event_listener(self):
        """
        Start the hotplug event listener thread.
        :return:
        """
        if platform.system() == 'Windows':
            self._event_thread = threading.Thread(target=self._handle_hotplug_event_windows, daemon=True)
        else:  # Linux
            res = libusb.hotplug_register_callback(self._lib_context,
                                                   libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED | libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT,  # noqa!
                                                   libusb.LIBUSB_HOTPLUG_NO_FLAGS,
                                                   VENDOR_ID, PRODUCT_ID,
                                                   libusb.LIBUSB_HOTPLUG_MATCH_ANY,
                                                   _hotplug_event_callback,
                                                   ctypes.byref(self._user_context),
                                                   ctypes.byref(self._callback_handle))
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError('Failed to register hotplug callback')
            self._event_thread = threading.Thread(target=self._handle_hotplug_event, daemon=True)

        self.event_thread_running = True
        self._event_thread.start()

    def stop_hotplug_event_listener(self):
        """
        Stop the hotplug event listener thread.
        :return:
        """
        self.event_thread_running = False
        self._event_thread.join()

        libusb.hotplug_deregister_callback(self._lib_context, self._callback_handle)
        libusb.exit(self._lib_context)

    def _handle_hotplug_event(self):
        """
        Handle hotplug events.
        :return:
        """
        while self.event_thread_running:
            res = libusb.handle_events_timeout_completed(self._lib_context,
                                                         libusb.timeval(0, 100000),
                                                         None)
            if res != libusb.LIBUSB_SUCCESS:
                log.error(f'Failed to handle libusb events: {libusb.error_name(res)}')
                continue

            # handle new devices
            new_devs = self._user_context.new_devs
            while len(new_devs) > 0:
                dev = new_devs.pop()
                dev_address = libusb.get_device_address(dev)
                descriptors = self._get_device_descriptor(dev)
                self._add_device(dev_address, descriptors)

            # handle removed devices
            removed_devs = self._user_context.removed_devs
            while len(removed_devs) > 0:
                dev = removed_devs.pop()
                dev_address = libusb.get_device_address(dev)
                self._remove_device(dev_address)

    def _handle_hotplug_event_windows(self):
        """
        Libusb does not have hot plug support on Windows.
        This function is a workaround by polling for connected devices.
        :return:
        """
        while self.event_thread_running:
            # Enumerate all devices
            device_list_p = ctypes.POINTER(ctypes.POINTER(libusb.device))()
            res = libusb.get_device_list(self._lib_context, ctypes.byref(device_list_p))
            if res < libusb.LIBUSB_SUCCESS:
                log.error('Failed to get device list')
                return

            device_maps = {}
            for i in range(res):
                dev = device_list_p[i]
                descriptors = self._get_device_descriptor(dev)
                if not descriptors or (
                        descriptors[0].vendor_id != VENDOR_ID and descriptors[0].product_id != PRODUCT_ID):
                    continue

                device_maps[libusb.get_device_address(dev)] = descriptors

            new_dev_addresses = set(device_maps.keys())
            current_dev_addresses = set(self._libusb_devs.keys())

            # handle new devices
            added_devs = new_dev_addresses - current_dev_addresses
            for dev_address in added_devs:
                self._add_device(dev_address, device_maps[dev_address])

            # handle removed devices
            removed_devs = current_dev_addresses - new_dev_addresses
            for dev_address in removed_devs:
                self._remove_device(dev_address)

            # Sleep here so we're not constantly polling
            time.sleep(0.1)

    @staticmethod
    def _get_device_descriptor(dev) -> Optional[List[DeviceDescriptor]]:
        """
        Get the device descriptor for a given device.
        :param dev:
        :return:
        """
        desc = libusb.device_descriptor()
        res = libusb.get_device_descriptor(dev, ctypes.byref(desc))
        if res != libusb.LIBUSB_SUCCESS:
            log.debug(f'Failed to get device descriptor: {libusb.error_name(res)}')
            return None

        dh = ctypes.POINTER(libusb.device_handle)()
        res = libusb.open(dev, ctypes.byref(dh))
        if res != libusb.LIBUSB_SUCCESS:
            log.debug(f'Failed to open libusb device: {libusb.error_name(res)}')
            return None

        try:
            # Get serial number string
            sn_bfr = (ctypes.c_ubyte * 512)()
            ctypes.memset(sn_bfr, 0, ctypes.sizeof(sn_bfr))
            res = libusb.get_string_descriptor_ascii(dh, desc.iSerialNumber, sn_bfr, ctypes.sizeof(sn_bfr))
            if res < 2:
                log.debug(f'Failed to get serial number: {libusb.error_name(res)}')
                return None
            sn_str = ctypes.cast(sn_bfr, ctypes.c_char_p)
            if sn_str.value is None:
                return None

            serial_number = sn_str.value.decode("ascii")
            # Find all interfaces using the hidapi library to get proper paths to interfaces since libusb has does not
            # provide this information.
            return hid_enum_dev_by_sn(serial_number)
        finally:
            libusb.close(dh)
