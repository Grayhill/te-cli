import ctypes
import time
from math import modf
from typing import List

import libusb


class DevDsc:
    vid: int
    pid: int
    sn: str

    def __init__(self, vid: int, pid: int, sn: str = ""):
        self.vid = vid
        self.pid = pid
        self.sn = sn

    def __key(self):
        return self.vid, self.pid, self.sn

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


def wait_hotplug_event(devs: List[DevDsc], timeout: float) -> List[DevDsc]:
    libctx = ctypes.POINTER(libusb.context)()
    res = libusb.init(ctypes.byref(libctx))
    if res < 0:
        raise RuntimeError()

    ctx = HotPlugCtx([])
    ndevs = len(devs)

    # Get rid of duplicates to preventmultiple notifications for one device
    for d in devs:
        # SN is not used for matching therefore we must not use it when ridding the dups
        d.sn = ""
    devs = list(set(devs))

    try:
        cbhl: list[ctypes.c_int] = []
        for d in devs:
            cbh = libusb.hotplug_callback_handle()
            res = libusb.hotplug_register_callback(libctx,
                                                   libusb.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED,
                                                   libusb.LIBUSB_HOTPLUG_NO_FLAGS,
                                                   d.vid, d.pid,
                                                   libusb.LIBUSB_HOTPLUG_MATCH_ANY,
                                                   _hotplug_event,
                                                   ctypes.byref(ctx),
                                                   ctypes.byref(cbh))
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            cbhl.append(cbh)

        while timeout > 0 and len(ctx.devs) < ndevs:
            tv = _timeout_to_tv(timeout)
            start = time.time()

            res = libusb.handle_events_timeout_completed(libctx, ctypes.byref(tv), None)
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            timeout -= time.time() - start

        for cbh in cbhl:
            libusb.hotplug_deregister_callback(libctx, cbh)

        devs = []
        for d in ctx.devs:
            desc = libusb.device_descriptor()
            res = libusb.get_device_descriptor(d, ctypes.byref(desc))

            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            dh = ctypes.POINTER(libusb.device_handle)()
            res = libusb.open(d, ctypes.byref(dh))
            if res != libusb.LIBUSB_SUCCESS:
                raise RuntimeError()

            try:
                bfr = (ctypes.c_ubyte * 512)()
                ctypes.memset(bfr, 0, ctypes.sizeof(bfr))
                res = libusb.get_string_descriptor_ascii(dh, desc.iSerialNumber, bfr, ctypes.sizeof(bfr))
                if res < 2:
                    raise RuntimeError()

                _str = ctypes.cast(bfr, ctypes.c_char_p)
                if _str.value is not None:
                    devs.append(DevDsc(desc.idVendor, desc.idProduct, _str.value.decode("ascii")))

            finally:
                libusb.close(dh)

    finally:
        libusb.exit(libctx)

    return devs
