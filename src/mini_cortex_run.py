from lib import FPGA_controler
from lib.LED_cube import send_LED_cube_animate
import json
import argparse
import time
import os

# We parse comand line arguments. If mini_cortext.py is executed directly from
# the comand line, default_init.json will be loaded. If -i is provided with a
# path to an init.json file, that file's contents will be read into the program
#
# These json files provide environment variable that are used for setup and 
# throughout the program.
parser = argparse.ArgumentParser()
parser.add_argument(
    "-i", "--init", 
    action="store", 
    default="default_init.json"
)

args = vars(parser.parse_args())

with open(args["init"]) as f:
    env_args = json.load(f)

# Set env variables
EVENT_ENABLE = env_args["EVENT_ENABLE"]
MONITOR_ENABLE = env_args["MONITOR_ENABLE"]
TIME_STR = time.strftime("%Y-%m-%d_%H:%M")

print(f"Date_Time: {TIME_STR}\n")
print(f"Loaded {args['init'].split('/')[-1]}")
print(f"{env_args}\n")

# Pass env varibales to the FPGA_controler script and send setup to the FPGA
FPGA_controler.init(env_args)
FPGA_controler.tx_setup()
print("Setup sent to FPGA...")


# Event mode body. Data is saved from the FPGA, currently 32 bits are returned,
# im not sure why but thats how it is in mdaq_v2.py and mdaq_startup_v2.py. 
# Should return pixel data from the FPGA which would be 27 bits for 3x3x3 
# detector.
#
# Creates the data file to save data for archiving. Continualy querries the
# FPGA for event data. Saves and displays captured data
if EVENT_ENABLE == 1:
    os.makedirs("data/event/", exist_ok=True)
    event_data_file = open(f"data/event/{TIME_STR}.csv", "w")
    event_data_file.write("Time,Data\n")

    print("Starting event mode!\n")
    while True:
        event_data = FPGA_controler.event_handler()
        event_time = time.strftime("%y-%m-%d_%H:%M:%S")
        event_data_file.write(f"{event_time},{event_data:032b}\n")

        send_LED_cube_animate(f"{event_data:032b}")

        print ("Timestamp and Event",event_time.split("_")[-1])   
        print(f"{event_data:032b}")


# Monitor mode body. Creates data file to save data for archiving. Continualy
# querries the FPGA for monitor data. Saves and prints captured data
if MONITOR_ENABLE == 1:
    os.makedirs("data/monitor/", exist_ok=True)
    monitor_data_file = open(f"data/monitor/{TIME_STR}.csv", "w")
    monitor_data_file.write("Time,Data\n")

    print("Starting monitor mode!\n")
    while True:
        monitor_data = FPGA_controler.monitor_handler()
        monitor_time = time.strftime("%y-%m-%d_%H:%M:%S")
        monitor_data_file.write(f"{monitor_time},{str(monitor_data)}\n")

        print(f"Time: {monitor_time}\
              \nTrigger rate: {monitor_data[18]}"
        )
        for idx in range(len(monitor_data)):
            print(f"Ch{idx+1}", end="\t")
        print("")
        for value in monitor_data:
            print(f"{value}", end="\t")
        print("\n\n")