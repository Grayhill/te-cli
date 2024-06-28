import argparse

import sys

from te.cli.core import CLICore


def create_parser() -> argparse.ArgumentParser:
    cli_core = CLICore()
    parser = argparse.ArgumentParser(prog="Touch Encoder CLI",
                                     usage='te',
                                     description="Interact with Touch Encoder")

    parser.add_argument('-v', '--version', action='store_true',
                        help='List the version of the tools in the toolbox')

    cmd_parsers = parser.add_subparsers(title='Commands')

    # restart_parser.add_argument('--id', required=False,
    #                            help='ID of TE to reboot')

    ls_parser = cmd_parsers.add_parser('ls', help='List all connected TE devices')
    ls_parser.set_defaults(func=cli_core.ls)

    info_parser = cmd_parsers.add_parser('info', help='List info of the selected TE device')
    info_parser.set_defaults(func=cli_core.info)

    # Restart CLI
    restart_parser = cmd_parsers.add_parser('restart', help='Restart TE device')
    restart_parser.add_argument('-u', '--utility', action='store_true', required=False, dest='to_utility',
                                help='Restart TE to utility app')
    restart_parser.add_argument('--hid', action='store_true', required=False, dest='hid_tes',
                                help='Restart only HID USB TEs')
    restart_parser.add_argument('--can', action='store_true', required=False, dest='can_tes',
                                help='Restart only CAN J1939 TEs')
    restart_parser.add_argument('--all', action='store_true', required=False, dest='all_tes',
                                help='Restart only CAN J1939 TEs')
    restart_parser.set_defaults(func=cli_core.restart)

    # Update CLI
    update_parser = cmd_parsers.add_parser('update', help='Update TE device')
    update_parser.add_argument('filepath',
                               help='tepkg for update')
    update_parser.add_argument('--hid', action='store_true', required=False, dest='hid_tes',
                               help='Update only HID USB TEs')
    update_parser.add_argument('--can', action='store_true', required=False, dest='can_tes',
                               help='Update only CAN J1939 TEs')
    update_parser.add_argument('--all', action='store_true', required=False, dest='all_tes',
                               help='Update only CAN J1939 TEs')
    update_parser.set_defaults(func=cli_core.update)

    # GUIDE Interface
    screen_parser = cmd_parsers.add_parser('screen', help='Set or get TE screen')
    screen_parser.add_argument('-g', '--get', action='store_true', required=False, dest='get_screen',
                               help='Get the current screen on TE')
    screen_parser.add_argument('-s', '--set', action='store_true', required=False, dest='set_screen',
                               help='Set the screen on TE')
    screen_parser.add_argument('-sid', '--screen-id', type=int, required='--set' in sys.argv, dest='screen_id',
                               help='The screen ID to set, required for setting screen')
    screen_parser.set_defaults(func=cli_core.screen)

    var_parser = cmd_parsers.add_parser('variable', help='Set or get a variable on TE screen')
    var_parser.add_argument('-g', '--get', action='store_true', required=False, dest='get_var',
                            help='Get the variable value from the TE')
    var_parser.add_argument('-s', '--set', action='store_true', required=False, dest='set_var',
                            help='Set the variable value on the TE')
    var_parser.add_argument('-sid', '--screen-id', type=int, required=True, dest='screen_id',
                            help='The screen ID of where variable is located')
    var_parser.add_argument('-vid', '--variable-id', type=int, required=True, dest='var_id',
                            help='The variable ID to set')
    var_parser.add_argument('-iv', '--int-value', type=int, required='--set' in sys.argv, dest='var_val',
                            help='The variable int value to set, required for setting variable value')
    var_parser.add_argument('-sv', '--str-value', type=str, required='--set' in sys.argv, dest='var_val',
                            help='The variable string value to set, required for setting variable value')
    var_parser.set_defaults(func=cli_core.variable)

    brightness_parser = cmd_parsers.add_parser('set-brightness', help='Set brightness of TE')
    brightness_parser.add_argument('-l', '--level', type=int, required=True, dest='level',
                                   help='Level of brightness')
    brightness_parser.add_argument('--store', action='store_true', required=False, dest='store',
                                   help='Store new brightness level on device')
    brightness_parser.set_defaults(func=cli_core.set_brightness)

    return parser


def main():
    parser = create_parser()

    args = parser.parse_args()

    args_dict = args.__dict__.copy()

    # Top level CLI
    # Handle version CLI
    if args_dict['version']:
        CLICore.version()
        return
    del args_dict['version']

    # Print help and exit if there are no params after top level options
    if not args_dict:
        parser.print_help()
        exit()

    # Commands CLI
    del args_dict['func']
    args.func(**args_dict)
    # FUNC_MAP[args]


if __name__ == '__main__':
    main()
