import smbus
import time

class BMP180:
    """
    Driver for the Bosch BMP180 temperature/pressure sensor.
    Usage:
        sensor = BMP180(oss=1)
        print(sensor.temperature_c)
        print(sensor.pressure_hpa)
        print(sensor.altitude_m)
    """
    
    BMP180_ADDR = 0x77
    REG_CALIB   = 0xAA
    REG_CONTROL = 0xF4
    REG_DATA    = 0xF6
    CMD_TEMP    = 0x2E

    #OSS(control byte, conversion delay in seconds)
    _OSS_SETTINGS = {
        0: (0x34, 0.005),
        1: (0x74, 0.008),
        2: (0xB4, 0.014),
        3: (0xF4, 0.026),
    }

    def __init__(self, bus_number=1, oss=1, sea_level_pa=101325.0):
        """
        Args:
            oss:          Oversampling setting 0-3
                            0 = low power, 1 = standard,
                            2 = high res,  3 = ultra high res.
            sea_level_pa: Reference pressure used for altitude calculation (Pa).
        """
        if oss not in self._OSS_SETTINGS:
            raise ValueError(f"oss must be 0, 1, 2, or 3 — got {oss}")

        self.oss          = oss
        self.sea_level_pa = sea_level_pa
        self._bus         = smbus.SMBus(bus_number)
        self._cal         = self._read_calibration()


    def _read_calibration(self):
        raw = self._bus.read_i2c_block_data(self.BMP180_ADDR, self.REG_CALIB, 22)

        def s16(hi, lo):
            val = (hi << 8) | lo
            return val - 65536 if val > 32767 else val

        def u16(hi, lo):
            return (hi << 8) | lo

        return {
            'AC1': s16(raw[0],  raw[1]),
            'AC2': s16(raw[2],  raw[3]),
            'AC3': s16(raw[4],  raw[5]),
            'AC4': u16(raw[6],  raw[7]),  
            'AC5': u16(raw[8],  raw[9]),   
            'AC6': u16(raw[10], raw[11]),  
            'B1':  s16(raw[12], raw[13]),
            'B2':  s16(raw[14], raw[15]),
            'MB':  s16(raw[16], raw[17]),
            'MC':  s16(raw[18], raw[19]),
            'MD':  s16(raw[20], raw[21]),
        }

    def _read_raw_temperature(self):
        self._bus.write_byte_data(self.BMP180_ADDR, self.REG_CONTROL, self.CMD_TEMP)
        time.sleep(0.005)
        data = self._bus.read_i2c_block_data(self.BMP180_ADDR, self.REG_DATA, 2)
        return (data[0] << 8) | data[1]

    def _read_raw_pressure(self):
        ctrl_byte, delay = self._OSS_SETTINGS[self.oss]
        self._bus.write_byte_data(self.BMP180_ADDR, self.REG_CONTROL, ctrl_byte)
        time.sleep(delay)
        data = self._bus.read_i2c_block_data(self.BMP180_ADDR, self.REG_DATA, 3)
        return ((data[0] << 16) | (data[1] << 8) | data[2]) >> (8 - self.oss)

    def _compensate(self):
        cal = self._cal
        UT  = self._read_raw_temperature()
        UP  = self._read_raw_pressure()

        X1 = (UT - cal['AC6']) * cal['AC5'] / 32768.0
        X2 = cal['MC'] * 2048.0 / (X1 + cal['MD'])
        B5 = X1 + X2
        temp_c = (B5 + 8.0) / 16.0 / 10.0

        B6 = B5 - 4000.0

        X1 = (cal['B2'] * (B6 * B6 / 4096.0)) / 2048.0
        X2 = cal['AC2'] * B6 / 2048.0
        X3 = X1 + X2
        B3 = (((int(cal['AC1'] * 4 + X3) << self.oss) + 2) / 4.0)

        X1 = cal['AC3'] * B6 / 8192.0
        X2 = (cal['B1'] * (B6 * B6 / 4096.0)) / 65536.0
        X3 = (X1 + X2 + 2.0) / 4.0
        B4 = cal['AC4'] * (X3 + 32768.0) / 32768.0

        B7 = (UP - B3) * (50000 >> self.oss)
        p  = (B7 * 2 / B4) if B7 < 2147483648 else (B7 / B4 * 2)

        X1 = (p / 256.0) ** 2
        X1 = (X1 * 3038.0) / 65536.0
        X2 = (-7357.0 * p) / 65536.0
        pressure_pa = p + (X1 + X2 + 3791.0) / 16.0

        return temp_c, pressure_pa

    def read(self):
        temp_c, pressure_pa = self._compensate()
        altitude_m = 44330.0 * (1.0 - (pressure_pa / self.sea_level_pa) ** 0.1903)

        return {
            'temperature_c':  round(temp_c, 2),
            'temperature_f':  round(temp_c * 1.8 + 32.0, 2),
            'pressure_pa':    round(pressure_pa, 2),
            'pressure_hpa':   round(pressure_pa / 100.0, 2),
            'altitude_m':     round(altitude_m, 2),
            'altitude_ft':    round(altitude_m * 3.28084, 2),
        }

    def safe_read(self):
        try:
            return self.read()
        except Exception as e:
            print(f"WARNING: BMP180 read failed: {e}")
            return {
                'temperature_c': None,
                'temperature_f': None,
                'pressure_pa':   None,
                'pressure_hpa':  None,
                'altitude_m':    None,
                'altitude_ft':   None,
            }
            
    @property
    def temperature_c(self):
        """Current temperature in Celsius."""
        return round(self._compensate()[0], 2)

    @property
    def temperature_f(self):
        """Current temperature in Fahrenheit."""
        return round(self.temperature_c * 1.8 + 32.0, 2)

    @property
    def pressure_pa(self):
        """Current pressure in Pascals."""
        return round(self._compensate()[1], 2)

    @property
    def pressure_hpa(self):
        """Current pressure in hectopascals (millibars)."""
        return round(self.pressure_pa / 100.0, 2)

    @property
    def altitude_m(self):
        """Estimated altitude in metres based on sea_level_pa reference."""
        return round(44330.0 * (1.0 - (self.pressure_pa / self.sea_level_pa) ** 0.1903), 2)

    @property
    def altitude_ft(self):
        """Estimated altitude in feet."""
        return round(self.altitude_m * 3.28084, 2)

    def __repr__(self):
        return f"BMP180(oss={self.oss}, addr=0x{self.BMP180_ADDR:02X})"


#Example
# if __name__ == '__main__':
#     sensor = BMP180(oss=1)
#     data = sensor.read()

#     print(f"Temperature  : {data['temperature_c']} °C  /  {data['temperature_f']} °F")
#     print(f"Pressure     : {data['pressure_hpa']} hPa  ({data['pressure_pa']} Pa)")
#     print(f"Altitude     : {data['altitude_m']} m  /  {data['altitude_ft']} ft")