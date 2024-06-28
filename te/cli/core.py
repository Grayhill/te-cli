import os
import sys
from enum import Enum
from threading import Thread
from typing import List, Optional, Union

from rich import box
from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.table import Table, Column
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TextColumn

from te import VERSION
from te.utils import discovery_tool
from te.cli import cli_utility
from te.cli.cli_utility import generate_restart_status_table
from te.interface.common import Status, ScreenID, VariableID, VariableData, Update
from te.interface import TouchEncoder


class CLICore:

    @staticmethod
    def ls(*args):
        devices = discovery_tool.pprint_discover_tes()
        cli_utility.pprint_devices(devices)
        cli_utility.disconnect_devices(devices)

    @staticmethod
    def info(*args):
        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        selected_devices: List[TouchEncoder] = cli_utility.pprint_device_selection(devices)
        if not selected_devices:
            sys.exit()

        device: TouchEncoder = selected_devices[0]

        table = Table(box=box.ROUNDED, show_header=False)
        version_map = {
            'Hardware ID': device.hardware_id,
            'Firmware Version': f'v{device.version.firmware}',
            'Bootloader Version': f'v{device.version.bootloader}',
            'Project Info': str(device.project_info),
        }

        for key, value in version_map.items():
            table.add_row(key, value)

        console = Console()
        console.print(table)
        device.disconnect()

    @staticmethod
    def set_brightness(level: int, store: bool = False):
        console = Console()

        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        selected_devices: List[TouchEncoder] = cli_utility.pprint_device_selection(devices)
        if not selected_devices:
            sys.exit()

        device: TouchEncoder = selected_devices[0]
        status = device.set_brightness(level, store)
        device.disconnect()
        if status == Status.SUCCESS:
            console.print(f'Successfully set brightness to {level}.')
            return
        console.print(f'Could not set brightness to {level}')

    @staticmethod
    def screen(get_screen: bool = False, set_screen: bool = False, screen_id: Optional[int] = None):
        console = Console()
        if not get_screen and not set_screen:
            console.print('No parameters provided. See \'te screen -h\' for help.')
            sys.exit()

        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        selected_devices: List[TouchEncoder] = cli_utility.pprint_device_selection(devices)
        if not selected_devices:
            sys.exit()

        device: TouchEncoder = selected_devices[0]
        if get_screen:
            screen_id = device.guide.get_screen()
            console.print(f'Current Screen ID :arrow_right-text: {screen_id}')
            sys.exit()

        status = device.guide.set_screen(ScreenID(screen_id))
        if status == Status.SUCCESS:
            console.print(f'Screen successfully set to {screen_id}')
        else:
            console.print(f'Could not set screen to {screen_id}', style=Style(color='red'))

    @staticmethod
    def variable(get_var: bool = False, set_var: bool = False, screen_id: Optional[int] = None,
                 var_id: Optional[int] = None, var_val: Union[int, str, None] = None):
        console = Console()
        if not get_var and not set_var:
            console.print('No parameters provided. See \'te variable -h\' for help.')
            return

        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        selected_devices: List[TouchEncoder] = cli_utility.pprint_device_selection(devices)
        if not selected_devices:
            sys.exit()

        device: TouchEncoder = selected_devices[0]
        if get_var:
            var_val = device.guide.get_var(ScreenID(screen_id), VariableID(var_id))
            if var_val != Status.ERROR:
                console.print(f'Screen {screen_id} - Variable {var_id} :arrow_right-text: Val {var_val.to_int()}')
            else:
                console.print(f'Screen {screen_id} - Variable {var_id} :arrow_right-text: Could not get val')
            return

        status = device.guide.set_var(ScreenID(screen_id), VariableID(var_id), VariableData(var_val))
        if status == Status.SUCCESS:
            console.print(f'Screen {screen_id} - Variable {var_id} :arrow_right-text: val set to {var_val}')
        else:
            console.print(f'Screen {screen_id} - Variable {var_id} :arrow_right-text: Could not set val to {var_val}',
                          style=Style(color='red'))

    @staticmethod
    def restart(all_tes=None, hid_tes=None, can_tes=None, to_utility=None):
        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        if not devices:
            sys.exit()

        selected_devices = cli_utility.pprint_device_selection(devices, all_tes=all_tes, hid_tes=hid_tes,
                                                               can_tes=can_tes)
        d_map = {}
        for d in selected_devices:
            d_map[d] = 'Waiting'
        with Live(generate_restart_status_table(d_map), refresh_per_second=20) as live:
            def restart_device(_dev):
                d_map[_dev] = _dev.restart(to_utility=to_utility, authenticate=to_utility).value
                live.update(generate_restart_status_table(d_map))

            threads = []
            for dev in selected_devices:
                d_map[dev] = 'Restarting'
                live.update(generate_restart_status_table(d_map))
                t = Thread(target=restart_device, args=(dev,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        cli_utility.disconnect_devices(devices)

    @staticmethod
    def update(filepath, all_tes=None, hid_tes=None, can_tes=None):
        if not os.path.exists(filepath):
            print(f'Could not find update file at provided filepath: {filepath}')
            return
        file_ext = os.path.splitext(filepath)[1]
        if file_ext != '.tepkg' and file_ext != '.zip':
            print('Provided update file is invalid. Accepted file types are: .tepkg or .zip')
            return

        devices: [TouchEncoder] = discovery_tool.pprint_discover_tes()
        selected_devices = cli_utility.pprint_device_selection(devices, all_tes=all_tes, hid_tes=hid_tes,
                                                               can_tes=can_tes)

        # Create progress status table
        table = Table('#', 'Device', 'Interface', 'Status', box=box.SIMPLE)
        dev_prog_map = {}
        for i, dev in enumerate(selected_devices):
            progress = Progress(
                SpinnerColumn(),
                BarColumn(pulse_style='grey50', complete_style='navajo_white1'),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TextColumn('{task.description}', table_column=Column(min_width=15)),
            )
            table.add_row(str(i), dev.NAME, dev.interface, progress, style=cli_utility.get_color(dev))
            task_id = progress.add_task('Waiting', start=False)
            dev_prog_map[dev] = (progress, task_id)

        with Live(table, refresh_per_second=20):
            threads = []
            for dev in selected_devices:

                def update_dev(_dev):
                    _progress, _task_id = dev_prog_map[_dev]

                    def progress_cb(desc: Enum, completed=None, total=None):
                        desc_pretty = desc.name.replace('_', ' ').capitalize()
                        if total and completed:
                            _progress.update(task_id=_task_id, description=f'[yellow]{desc_pretty}', total=total + 1,
                                             completed=completed)
                        else:
                            _progress.update(task_id=_task_id, description=desc_pretty)

                    _progress.start_task(task_id=_task_id)
                    status = _dev.update(filepath=filepath, progress_cb=progress_cb)
                    status_pretty = status.name.replace('_', ' ').capitalize()
                    if status == Update.Status.ERROR:
                        status_pretty = f'[red]{status_pretty}'
                    _progress.update(task_id=_task_id, description=status_pretty,
                                     completed=0 if 'SUCCESS' not in status.name else 100, total=100)
                    _progress.stop_task(task_id=_task_id)
                    _dev.disconnect()

                t = Thread(target=update_dev, args=(dev,), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        sys.exit()

    @staticmethod
    def version():
        console = Console()
        console.print(f'TouchEncoder CLI v{VERSION}')
