import logging
from typing import List, Dict

import hid as hidapi

from te.interface.hid import HIDTouchEncoder


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


def discover_tes() -> List[HIDTouchEncoder]:
    """
    Search for all HID USB Touch Encoders.
    :return:
    """
    sn_map = hid_enumerate()

    tes = []
    for sn, i_face in sn_map.items():
        if len(i_face) < 1:
            logging.warning(f'Bogus TE {i_face}')
        try:
            new_te = HIDTouchEncoder(i_face, serial_number=sn)
            tes.append(new_te)
        except OSError:
            logging.error(f'Could not initialize usb:{sn}. Device could be busy.')

    return tes
