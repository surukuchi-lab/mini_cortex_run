#! /usr/local/bin/python3

import subprocess as sb
import serial
import json
# import os

# DO NOT CHANGE default 0x06
pulse_width = 6 # 0x06

event_enable = int(input("Event mode enable [0, 1]: "))
mon_enable = int(input("Monitor mode enable [0, 1]: "))
if mon_enable == 0: mon_period = 0
else: mon_period = int(input("Enter monitoring period: "))

fpga_usb_num = input("Enter USB PORT NO: ")  
fpga_ser = f"/dev/ttyUSB{fpga_usb_num}"



# Input Checks
print("\nChecking config...")

# Check exclusivity of monitor and event modes ...
# may be removed in future when FPGA firmware is updated
if mon_enable == event_enable:
    raise ValueError("Monitor and event modes cannot be active at the same time")

# Check if modes are either 0 or 1
if mon_enable not in (0, 1):
    raise ValueError("Monitor mode must be either 0 or 1")
if event_enable not in (0, 1):
    raise ValueError("Event mode must be either 0 or 1")

# Test serial connection
try: serial.Serial(fpga_ser, 115200, timeout=0)
except serial.serialutil.SerialException:
    import serial.tools.list_ports
    print(f"Device not found on {fpga_ser}\
          \nPrinting available devices...\n")
    for i in serial.tools.list_ports.comports():
        print(i)
    # have user manually enter the correct path
    fpga_ser = input("Enter full path or Ctl-C to exit: ")


print("\nConfig passed.\
      \nCreating init file")

config = {
    "EVENT_ENABLE": event_enable,
    "MONITOR_ENABLE": mon_enable,
    "MONITOR_PERIOD": mon_period,
    "FPGA_SER_PATH": fpga_ser, 
    "PULSE_WIDTH": pulse_width,
}

# Will overwrite your init.json if you haven't renamed it
sb.call("touch init.json")
with open("init.json", "w") as f:
    json.dump(config, f, indent=4)

print("Done! Starting mini CoRTEx")

sb.call("./run.sh -i init.json")
