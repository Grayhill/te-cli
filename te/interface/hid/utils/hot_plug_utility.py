import ctypes
import time
from math import modf
from typing import List

import libusb


class DevDsc:
    vid: int
    pid: int
    sn: str

    def __init__(self, vid: int, pid: int, sn: str = "", path: str = ""):
        self.vid = vid
        self.pid = pid
        self.sn = sn
        self.path = path

    def __key(self):
        return self.vid, self.pid, self.sn, self.path

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, rhs: 'DevDsc') -> bool:
        return isinstance(rhs, DevDsc) and \
            self.__key() == rhs.__key()


class HotPlugCtx(ctypes.Structure):
    _fields_ = [
        ("devs", ctypes.py_object)
    ]


@libusb.hotplug_callback_fn
def _hotplug_event(_, dev, event, user_data) -> int:
    ctx = ctypes.cast(user_data, ctypes.POINTER(HotPlugCtx)).contents

    if event == libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED:
        ctx.devs.append(dev)

    return 0


def _timeout_to_tv(timeout: float) -> libusb.timeval:
    t = modf(timeout)
    return libusb.timeval(int(t[1]), int(t[0] * 1000000))


def get_device_info(dev):
    desc = libusb.device_descriptor()
    res = libusb.get_device_descriptor(dev, ctypes.byref(desc))
    if res != libusb.LIBUSB_SUCCESS:
        raise RuntimeError()

    dh = ctypes.POINTER(libusb.device_handle)()
    res = libusb.open(dev, ctypes.byref(dh))
    if res != libusb.LIBUSB_SUCCESS:
        raise RuntimeError()

    try:
        bfr = (ctypes.c_ubyte * 512)()
        ctypes.memset(bfr, 0, ctypes.sizeof(bfr))
        res = libusb.get_string_descriptor_ascii(dh, desc.iSerialNumber, bfr, ctypes.sizeof(bfr))
        if res < 2:
            raise RuntimeError()

        _str = ctypes.cast(bfr, ctypes.c_char_p)
        if _str.value is None:
            return None

        port_numbers = (ctypes.c_uint8 * 7)()  # Maximum depth is 7
        path_length = libusb.get_port_numbers(dev, port_numbers, len(port_numbers))
        if path_length < 0:
            raise RuntimeError("Failed to get port numbers")
        bus_number = libusb.get_bus_number(dev)
        path = f"{bus_number}-" + ".".join(str(port_numbers[i]) for i in range(path_length))

        return DevDsc(desc.idVendor, desc.idProduct, _str.value.decode("ascii"), path)

    finally:
        libusb.close(dh)


def wait_hotplug_event(devs: List[DevDsc], timeout: float) -> List[DevDsc]:
    libctx = ctypes.POINTER(libusb.context)()
    res = libusb.init(ctypes.byref(libctx))
    if res < 0:
        raise RuntimeError()

    ctx = HotPlugCtx([])
    devs = list(set(devs))

    try:
        cbhl: list[ctypes.c_int] = []
        for d in devs:
            cbh = libusb.hotplug_callback_handle()
            res = libusb.hotplug_register_callback(libctx,
                                                   libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED | libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT,  # noqa!
                                                   libusb.LIBUSB_HOTPLUG_NO_FLAGS,
                                                   d.vid, d.pid,
                                                   libusb.LIBUSB_HOTPLUG_MATCH_ANY,
                                                   _hotplug_event,
                                                   ctypes.byref(ctx),
                                                   ctypes.byref(cbh))
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            cbhl.append(cbh)

        new_devs = []
        target_sns = {d.sn for d in devs}
        while timeout > 0 and len(new_devs) < len(devs):
            tv = _timeout_to_tv(timeout)
            start = time.time()

            res = libusb.handle_events_timeout_completed(libctx, ctypes.byref(tv), None)
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            timeout -= time.time() - start

            while len(ctx.devs) > 0:
                _dev_obj = ctx.devs.pop()
                d = get_device_info(_dev_obj)
                if d.sn in target_sns:
                    new_devs.append(d)

        for cbh in cbhl:
            libusb.hotplug_deregister_callback(libctx, cbh)

    finally:
        libusb.exit(libctx)

    return new_devs
