# Touch Encoder CLI

This repository contains the CLI for the Touch Encoder.

- [Requirements](#requirements)
- [Installation](#installation)
  - [Development](#development)
- [Usage](#usage)



## Requirements
- `Python >= 3.10` 

> [!IMPORTANT]
> **Windows**
> 
> Please make sure you have installed the [PEAK-System drivers](https://www.peak-system.com/Drivers.523.0.html?&L=1) for the CAN interface.
> 
> **Linux**
> 
> Please make sure you have set up the CAN network interface in your system. 

## Installation
A Python virtual environment (_venv_) is required to install the CLI tool.

### Development
```Shell
// Create venv
python3 -m venv </path/to/venv>

// Activate venv
. </path/to/venv>/bin/activate

// Install te-cli (replace `.` with `".[dev]"` to install dev dependencies)
python3 -m pip install .
```

## Usage
Run the following command to see the available options:
```Shell
$ te -h
usage: te

Interact with Touch Encoder

options:
  -h, --help            show this help message and exit
  -v, --version         List the version of the tools in the toolbox

Commands:
  {ls,info,restart,update,screen,variable,set-brightness}
    ls                  List all connected TE devices
    info                List info of the selected TE device
    restart             Restart TE device
    update              Update TE device
    screen              Set or get TE screen
    variable            Set or get a variable on TE screen
    set-brightness      Set brightness of TE
```

### Listing Devices
```Shell
$ te ls
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
```

### Getting Device Info
```Shell
$ te info
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 0
╭────────────────────┬────────────╮
│ Hardware ID        │ TE_RF_CAN  │
│ Firmware Version   │ v4.2.0     │
│ Bootloader Version │ v1.4.4     │
│ Project Info       │ UNKNOWN -1 │
╰────────────────────┴────────────╯
```

### Restarting Device
With the `te restart` command, Touch Encoders can be restarted individually, only HID, only CAN, or all. Additionally, you 
can restart them into utility app by providing the `--utility` option.

**Restart help**
```Shell
$ te restart -h
te restart -h
usage: te restart [-h] [-u] [--hid] [--can] [--all]

options:
  -h, --help     show this help message and exit
  -u, --utility  Restart TE to utility app
  --hid          Restart only HID USB TEs
  --can          Restart only CAN J1939 TEs
  --all          Restart only CAN J1939 TEs
````

```Shell
$ te restart
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 1
                                                 
  #   Device                Interface   Status   
 ─────────────────────────────────────────────── 
  0   J1939 Touch Encoder   can0:0xf2   Success
```

### Updating Device
Similar to restart, the `te update` command can update Touch Encoders individually, only HID, only CAN, or all. 
You can update the device's firmware (`<pkg_name>.tepkg`) and project (`<project_name>.zip`) by providing the file path.

**Update help**
```Shell
$ te update -h
usage: te update [-h] [--hid] [--can] [--all] filepath

positional arguments:
  filepath    tepkg for update

options:
  -h, --help  show this help message and exit
  --hid       Update only HID USB TEs
  --can       Update only CAN J1939 TEs
  --all       Update only CAN J1939 TEs
```

### Setting Screen Brightness
The `te set-brightness` command can set the brightness of the Touch Encoder.
The brightness level can be set between `0` and `100`. Additionally, you can store the new brightness level on the device 
so that it persists after a restart.
**Set brightness help**
```Shell
$ te set-brightness -h
usage: te set-brightness [-h] -l LEVEL [--store]

options:
  -h, --help            show this help message and exit
  -l LEVEL, --level LEVEL
                        Level of brightness
  --store               Store new brightness level on device
```

Example:
```Shell
$ te set-brightness -l 80
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 1
Successfully set brightness to 80.
```

### GUIDE Project Screen
You can set and get the screen on the Touch Encoder using the `te screen` command.
**Screen help**
```Shell
$ te screen -h
usage: te screen [-h] [-g] [-s] [-sid SCREEN_ID]

options:
  -h, --help            show this help message and exit
  -g, --get             Get the current screen on TE
  -s, --set             Set the screen on TE
  -sid SCREEN_ID, --screen-id SCREEN_ID
                        The screen ID to set, required for setting screen
```

**Getting Screen**
```Shell
$ te screen -g
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 0
Current Screen ID ➡︎ 2
```

**Setting Screen**
```Shell
$ te screen -s --screen-id 2
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 0
Screen successfully set to 2
```

### GUIDE Project Variable
You can set and get the variable on the Touch Encoder using the `te variable` command.
Currently, two types of variables are supported: `int` and `str`.
**Variable help**
```Shell
$ te variable -h
usage: te variable [-h] [-g] [-s] -sid SCREEN_ID -vid VAR_ID [-iv VAR_VAL] [-sv VAR_VAL]

options:
  -h, --help            show this help message and exit
  -g, --get             Get the variable value from the TE
  -s, --set             Set the variable value on the TE
  -sid SCREEN_ID, --screen-id SCREEN_ID
                        The screen ID of where variable is located
  -vid VAR_ID, --variable-id VAR_ID
                        The variable ID to set
  -iv VAR_VAL, --int-value VAR_VAL
                        The variable int value to set, required for setting variable value
  -sv VAR_VAL, --str-value VAR_VAL
                        The variable string value to set, required for setting variable value
```

**Getting Variable**
```Shell
$ te variable -g --screen-id 6 --variable-id 2
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 0
Screen 6 - Variable 2 ➡︎ 80
```


**Setting Variable**
```Shell
$ te variable -s --screen-id 6 --variable-id 2 --int-value 20
                                  Discovered Touch Encoders                                  
╭───┬─────────────────────┬───────────┬───────────┬────────┬────────┬──────────┬────────────╮
│ # │ Device              │ Interface │ HW ID     │ FW Ver │ BL Ver │ Proj Ver │ Proj Info  │
├───┼─────────────────────┼───────────┼───────────┼────────┼────────┼──────────┼────────────┤
│ 0 │ J1939 Touch Encoder │ can0:0xf2 │ TE_RF_CAN │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
│ 1 │ J1939 Touch Encoder │ can0:0xf3 │ TE_MX     │ 4.2.0  │ 1.4.4  │          │ UNKNOWN -1 │
╰───┴─────────────────────┴───────────┴───────────┴────────┴────────┴──────────┴────────────╯
Please select device [0]: 0
18E800F2 01 0B FF FF FF 00 EF 00
Screen 6 - Variable 2 ➡︎ 20
```
