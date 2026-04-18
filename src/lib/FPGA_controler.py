from array import array
import serial
import time

def init(env_args) -> None:
    global EVENT_ENABLE, MONITOR_ENABLE, MONITOR_PERIOD, FPGA_SER_PATH, PULSE_WIDTH, fpga_ser
    EVENT_ENABLE = env_args['EVENT_ENABLE']
    MONITOR_ENABLE = env_args['MONITOR_ENABLE']
    MONITOR_PERIOD = env_args['MONITOR_PERIOD']
    FPGA_SER_PATH = env_args['FPGA_SER_PATH']
    PULSE_WIDTH = 0x06 # env_args['PULSE_WIDTH']

    fpga_ser = serial.Serial(FPGA_SER_PATH,115200, timeout=0)

def tx_setup() -> None:
    '''Sends a data packet to the FPGA over the USART connection that is used to select mode and set other configurations'''
    tx_array = array('B',[]*200)

    # Defines the type of data the FPGA will output, monitor (23 bytes) or event mode (8 bytes)
    tx_array.append(MONITOR_ENABLE)
    tx_array.append(EVENT_ENABLE)

    tx_array.append(PULSE_WIDTH)
    tx_array.append(0xFF)
    tx_array.append(0x000000FF & MONITOR_PERIOD)
    tx_array.append((0x0000FF00 & MONITOR_PERIOD)>>8)
    tx_array.append((0x00FF0000 & MONITOR_PERIOD)>>16)
    tx_array.append((0xFF000000 & MONITOR_PERIOD)>>24)

    fpga_ser.write(bytes(tx_array))

def data_handler():
    while True:
        data = fpga_ser.readline()
        if len(data) == 8:
            return event_handler(data), True
        elif len(data) == 23:
            return monitor_handler(data), False
        else:
            time.sleep(0.005), None


def event_handler(data) -> int:
    rx_array = array('B', []*500)
    for byte in data:
        rx_array.append(byte)

    header      = ((rx_array[1] & 0x00ff) << 8) | (rx_array[0] & 0x00ff)
    event_tailer = ((rx_array[7] & 0x00ff) << 8) | (rx_array[6] & 0x00ff)

    if header == 0xa5a5 and event_tailer == 0xd5d5:
        eve_word = ((rx_array[5] & 0x000000ff) << 24) | ((rx_array[4] & 0x000000ff) << 16) \
                 | ((rx_array[3] & 0x000000ff) <<  8) |  (rx_array[2] & 0x000000ff)

        if type(eve_word) == int:
            return eve_word
        else:
            print(f"\033[91mError while processing bit string. Expected int type, got {type(eve_word)}\033[00m")
            return 0


def monitor_handler(data):
    rx_array = array('B', []*500)
    mon_array = array('f', []*50)

    for byte in data:
        rx_array.append(byte)

    header          = ((rx_array[1]  & 0x00ff) << 8) | (rx_array[0]  & 0x00ff)
    monitor_trailer = ((rx_array[22] & 0x00ff) << 8) | (rx_array[21] & 0x00ff)

    if header == 0xaaaa and monitor_trailer == 0xd6d6:
        for i in range(2, 21):
            mon_array.append(rx_array[i])
        return mon_array
