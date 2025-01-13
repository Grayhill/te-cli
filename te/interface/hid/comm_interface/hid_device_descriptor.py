from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceDescriptor:
    path: bytes
    vendor_id: int
    product_id: int
    serial_number: str
    interface_number: int
    release_number: Optional[int] = None
    manufacturer_string: Optional[str] = None
    product_string: Optional[str] = None
    usage_page: Optional[int] = None
    usage: Optional[int] = None
    bus_type: Optional[int] = None
