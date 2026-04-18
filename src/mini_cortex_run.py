from lib import FPGA_controler
from lib.LED_cube import send_LED_cube_animate
from lib.bmp180 import BMP180
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
TIME_STR = time.strftime("%Y-%m-%d_%H-%M")

print(f"Date_Time: {TIME_STR}\n")
print(f"Loaded {args['init'].split('/')[-1]}")
print(f"{env_args}\n")

#BMP180 sensor
try:
    bmp = BMP180(oss=3)
    print("BMP180 initialised.\n")
except Exception as e:
    bmp = None
    print(f"WARNING: BMP180 not available: environmental data will be omitted. ({e})\n")

# Pass env varibales to the FPGA_controler script and send setup to the FPGA
FPGA_controler.init(env_args)
FPGA_controler.tx_setup()
print("Setup sent to FPGA...")

#Setting up data files
#Event Data
os.makedirs("data/event/", exist_ok=True)
event_data_file = open(f"data/event/{TIME_STR}.csv", "w")
event_data_file.write("Time,Data,Temp_C,Pressure_hPa\n")
#Monitor Data
os.makedirs("data/monitor/", exist_ok=True)
monitor_data_file = open(f"data/monitor/{TIME_STR}.csv", "w")
channels = [f"ch{i}" for i in range(18)]
header   = ["Time"] + channels + ["Trig_rate", "Temp_C", "Pressure_hPa"]
monitor_data_file.write(",".join(header) + "\n")


#Core loop to get both event and monitor data
while True:
    data, isEventData = FPGA_controler.data_handler()
    if isEventData:
        if data is None:
            print(f"WARNING: No event data at {event_time}, skipping.")
            continue

        event_time = time.strftime("%y-%m-%d_%H-%M-%S")
        env = bmp.safe_read() if bmp else {k: None for k in ('temperature_c','pressure_hpa','altitude_m')}
 
        event_data_file.write(
            f"{event_time},"
            f"{data:032b},"
            f"{env['temperature_c']},"
            f"{env['pressure_hpa']}\n"
        )

        event_data_file.flush()

        send_LED_cube_animate(f"{data:032b}")

        print ("Timestamp and Event",event_time.split("_")[-1])   
        print(f"{data:032b}")
        if env['temperature_c'] is not None:
            print(
                f"Temp: {env['temperature_c']} °C  "
                f"| Pressure: {env['pressure_hpa']} hPa  "
            )

    elif not isEventData:
        monitor_time = time.strftime("%y-%m-%d_%H-%M-%S")
        env = bmp.safe_read() if bmp else {k: None for k in ('temperature_c','pressure_hpa','altitude_m')}
 
        monitor_data_file.write(
            f"{monitor_time},"
            f"{','.join(str(int(v)) for v in data[:18])},"
            f"{data[-1]},"
            f"{env['temperature_c']},"
            f"{env['pressure_hpa']}\n"
        )
        monitor_data_file.flush()
        if env['temperature_c'] is not None:
            print(
                f"Temp: {env['temperature_c']} °C  "
                f"| Pressure: {env['pressure_hpa']} hPa  "
            )
        print(f"Time: {monitor_time}\
            \nTrigger rate: {data[-1]}" # last hex word is the triger rate
        )
        for idx in range(len(data)-1):
            print(f"Ch{idx+1}", end="\t")
        print("")
        for value in data[:18]: # only the first 18 are scintilators
            print(f"{value}", end="\t")
        print("\n\n")

    else:
        print("Not Monitoring or Event Data?")
