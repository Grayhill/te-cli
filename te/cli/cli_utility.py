from typing import List

import sys
from rich import box
from rich.console import Console
from rich.spinner import Spinner
from rich.style import Style
from rich.table import Table
from rich.text import Text

from te.interface.hid import HIDTouchEncoder
from te.interface.j1939 import J1939TouchEncoder
from te.interface import TouchEncoder

err_style = Style(bold=True, color='red', italic=True)


def get_color(device):
    return 'bright_blue' if isinstance(device, HIDTouchEncoder) else 'bright_magenta'


def disconnect_devices(devices: List[TouchEncoder]):
    for device in devices:
        device.disconnect()


def pprint_devices(devices):
    """
    Pretty print devices into a nice table
    :param devices:
    :return:
    """
    to_print = Table('#', 'Device', 'Interface', 'HW ID', 'FW Ver', 'BL Ver', 'Proj Ver', 'Proj Info',
                     title='Discovered Touch Encoders', box=box.ROUNDED)

    if devices:
        for i, d in enumerate(devices):
            to_print.add_row(str(i), d.NAME, d.interface, d.hardware_id, d.version.firmware,
                             d.version.bootloader, d.version.project, str(d.project_info),
                             style=get_color(d))
    else:
        to_print = Text('No Touch Encoders were discovered.')
        to_print.stylize(style=Style(bold=True, color='red', italic=True))

    console = Console()
    console.print(to_print)


def pprint_device_selection(devices, all_tes=None, hid_tes=None, can_tes=None) -> List[TouchEncoder]:
    """
    Filter and/or ask user to select devices by printing a table
    :param devices:
    :param all_tes:
    :param hid_tes:
    :param can_tes:
    :return:
    """
    console = Console()

    if all_tes:
        return devices
    elif hid_tes:
        selected_devices = []
        for d in devices:
            if isinstance(d, HIDTouchEncoder):
                selected_devices.append(d)
        if not selected_devices:
            console.print('No HID Touch Encoders found.', style=err_style)
            sys.exit()
        return selected_devices
    elif can_tes:
        selected_devices = []
        for d in devices:
            if isinstance(d, J1939TouchEncoder):
                selected_devices.append(d)
        if not selected_devices:
            console.print('No CAN Touch Encoders found.', style=err_style)
            sys.exit()
        return selected_devices
    elif len(devices) > 1:
        pprint_devices(devices)
        selected = input('Please select device [0]: ')
        if selected:
            try:
                indices = selected.split(',')
                selected_devices = []
                for i in indices:
                    selected_devices.append(devices[int(i)])
                return selected_devices
            except IndexError:
                console.print(f'Incorrect device selected: {selected}', style=err_style)
                sys.exit()

    return [devices[0]]


def generate_restart_status_table(devs):
    table = Table('#', 'Device', 'Interface', 'Status', box=box.SIMPLE)
    for i, (d, status) in enumerate(devs.items()):
        if status == 'Restarting':
            status = Spinner('dots12', text=Text(status, style='bright_yellow'), style='bright_yellow')
        else:
            color = 'bright_red'
            if status == 'Success':
                color = 'bright_green'
            elif status == 'Waiting':
                color = 'bright_black'
            status = Text(status, style=color)
        table.add_row(str(i), d.NAME, d.interface, status, style=get_color(d))
    return table
