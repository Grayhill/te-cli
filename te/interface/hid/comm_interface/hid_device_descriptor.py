from dataclasses import dataclass


@dataclass
class DeviceDescriptor:
    vendor_id: int
    product_id: int
    serial_number: str
    interface_number: int
    path: bytes
