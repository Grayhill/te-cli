from typing import List, Dict

import hid as hidapi

from te.interface.hid import HIDTouchEncoder
from te.interface.hid.comm_interface.hid_manager import HIDManager


def hid_enumerate() -> Dict[str, List[Dict]]:
    sn_map = {}
    for i_face in hidapi.enumerate(vendor_id=HIDTouchEncoder.VENDOR_ID, product_id=HIDTouchEncoder.PRODUCT_ID):
        sn = i_face['serial_number']
        if not sn:
            continue
        if sn not in sn_map:
            sn_map[sn] = []
        sn_map[sn].append(i_face)
    return sn_map


def discover_tes() -> (HIDManager, List[HIDTouchEncoder]):
    """
    Search for all HID USB Touch Encoders.
    :return:
    """
    hid_manager = HIDManager()
    hid_manager.scan_for_interfaces()

    tes = []

    for sn in hid_manager.interfaces:
        new_te = HIDTouchEncoder(sn, hid_manager)
        tes.append(new_te)

    return hid_manager, tes
