from typing import List

from rich.console import Console

from te.utils import hid_utility
from te.utils import j1939_utility
from te.interface import TouchEncoder


def discover_touch_encoders(bitrate: int = 500000) -> List[TouchEncoder]:
    devices: List[TouchEncoder] = []
    # Discover CAN touch encoders
    devices += j1939_utility.discover_tes(bitrate=bitrate)

    # Discover HID touch encoders
    devices += hid_utility.discover_tes()

    return devices


def pprint_discover_tes():
    console = Console()
    with console.status('Discovering Touch Encoders...', spinner='bouncingBar', spinner_style='bright_yellow'):
        devices: List[TouchEncoder] = discover_touch_encoders()
        if len(devices) == 0:
            return []
        for d in devices:
            d.refresh_info()

    return devices
