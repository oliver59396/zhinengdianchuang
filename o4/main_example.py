"""import time
import dht
import math
from machine import Pin, ADC, UART

# ===================== Pin Definition =====================
# DHT22 Temperature & Humidity
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04 Ultrasonic
trig = Pin("P0_29", Pin.OUT)
echo = Pin("P1_23", Pin.IN)

# MQ Gas Sensors
mq135_ao = ADC(Pin("P4_12"))
mq135_do = Pin("P0_30", Pin.IN)
mq136_ao = ADC(Pin("P4_13"))
mq136_do = Pin("P1_21", Pin.IN)
mq7_ao = ADC(Pin("P0_14"))
mq7_do = Pin("P1_2", Pin.IN)

# ===================== ESP-01 WiFi Config (Fixed UART Pins) =====================
# 更换为MCXN947官方支持的UART1引脚 解决AF报错
wifi_uart = UART(1, baudrate=115200, tx=Pin("P1_17"), rx=Pin("P1_16"))
# ---------- Please Modify Your WiFi Info ----------
WIFI_SSID = "Your_WiFi_Name"
WIFI_PWD = "Your_WiFi_Password"
TCP_SERVER_IP = "127.0.0.1"
TCP_SERVER_PORT = 8080
# -------------------------------------------------
wifi_connected = False

# ===================== DHT22 Filter Parameters =====================
TEMP_OFFSET = -3.2
ALPHA_TEMP = 0.2
ALPHA_HUMI = 0.3
ewma_temp = None
ewma_humi = None

# ===================== MQ Sensor Parameters =====================
R0_135 = 150.0
R0_136 = 200.0
R0_7   = 60.0
RL = 10.0

A_135, B_135 = 116.6, -2.77
A_136, B_136 = 73.5, -1.82
A_7, B_7 = 99.05, -1.51

ALARM_135 = 300
ALARM_136 = 20
ALARM_7   = 50

# ===================== Helper Functions =====================
def safe_read_dht():
    for _ in range(3):
        try:
            dht_sensor.measure()
            t = dht_sensor.temperature()
            h = dht_sensor.humidity()
            if -40 < t < 80 and 0 < h < 100:
                return t, h
        except:
            time.sleep(0.5)
    return None, None

def read_gas(adc_pin):
    adc_val = adc_pin.read_u16()
    voltage = (adc_val / 65535) * 3.3
    return round(voltage, 2)

def voltage_to_ppm(voltage, R0, a, b):
    if voltage < 0.01:
        return 0.0
    Rs = RL * (3.3 - voltage) / voltage
    ratio = Rs / R0
    return max(0.0, min(10000.0, a * math.pow(ratio, b)))

def read_ultrasonic():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    timeout = 100000
    start = time.ticks_us()
    while echo.value() == 0 and (time.ticks_us() - start) < timeout:
        pass
    if echo.value() == 0:
        return 0.0

    echo_start = time.ticks_us()
    while echo.value() == 1 and (time.ticks_us() - echo_start) < timeout:
        pass
    if echo.value() == 1:
        return 0.0

    dist = (time.ticks_us() - echo_start) * 0.0343 / 2
    return round(dist, 1) if 2 < dist < 400 else 0.0

# ===================== WiFi Functions =====================
def wifi_send_at(cmd, timeout=1000):
    wifi_uart.write((cmd + "\r\n").encode())
    time.sleep_ms(50)
    resp = wifi_uart.read(timeout)
    return resp.decode('utf-8', 'ignore') if resp else ""

def esp01_init():
    global wifi_connected
    print("=== Initializing ESP-01 ===")
    wifi_send_at("AT+RST")
    time.sleep(2)
    wifi_send_at("AT")
    wifi_send_at("AT+CWMODE=1")
    time.sleep_ms(500)

    print(f"Connecting WiFi: {WIFI_SSID}")
    resp = wifi_send_at(f'AT+CWJAP="{WIFI_SSID}","{WIFI_PWD}"', 5000)
    if "WIFI CONNECTED" in resp or "OK" in resp:
        print("WiFi Connected OK")
        wifi_connected = True
    else:
        print("WiFi Connect Failed")
        return False

    time.sleep(1)
    resp = wifi_send_at(f'AT+CIPSTART="TCP","{TCP_SERVER_IP}",{TCP_SERVER_PORT}', 3000)
    if "CONNECT" in resp:
        print("TCP Connected OK")
        return True
    else:
        print("TCP Connect Failed")
        return False

def send_data_to_wifi(data):
    global wifi_connected
    if not wifi_connected:
        esp01_init()
        return
    try:
        wifi_uart.write(f'AT+CIPSEND={len(data)}\r\n'.encode())
        time.sleep_ms(50)
        wifi_uart.write(data.encode())
        print("Data Send OK via WiFi")
    except:
        print("Send Failed, Reconnecting...")
        wifi_connected = False

# ===================== System Init =====================
print("="*50)
print("FRDM-MCXN947 Multi-Sensor System")
print("="*50)
esp01_init()
time.sleep(2)

# ===================== Main Loop =====================
while True:
    # Read DHT22
    raw_t, raw_h = safe_read_dht()
    if raw_t is not None and raw_h is not None:
        cor_t = raw_t + TEMP_OFFSET
        if ewma_temp is None:
            ewma_temp = cor_t
            ewma_humi = raw_h
        else:
            ewma_temp = ALPHA_TEMP * cor_t + (1-ALPHA_TEMP) * ewma_temp
            ewma_humi = ALPHA_HUMI * raw_h + (1-ALPHA_HUMI) * ewma_humi
        temp = round(ewma_temp, 1)
        humi = round(ewma_humi, 1)
    else:
        temp, humi = 0.0, 0.0

    # Read Ultrasonic
    dist = read_ultrasonic()

    # Read Gas Sensors
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    
    mq135_ppm = voltage_to_ppm(mq135_v, R0_135, A_135, B_135)
    mq136_ppm = voltage_to_ppm(mq136_v, R0_136, A_136, B_136)
    mq7_ppm = voltage_to_ppm(mq7_v, R0_7, A_7, B_7)
    
    mq135_al = 1 if mq135_ppm > ALARM_135 else 0
    mq136_al = 1 if mq136_ppm > ALARM_136 else 0
    mq7_al = 1 if mq7_ppm > ALARM_7 else 0

    # WiFi Data Package
    send_data = f"T:{temp}C|H:{humi}%|D:{dist}cm|MQ135:{mq135_ppm:.1f}|MQ136:{mq136_ppm:.1f}|MQ7:{mq7_ppm:.1f}"
    send_data_to_wifi(send_data)

    # Serial Print
    print("="*50)
    print(f"Temp:{temp:>5.1f}C | Humid:{humi:>5.1f}% | Dist:{dist:>5.1f}cm")
    print(f"MQ135(Air):{mq135_ppm:>6.1f}PPM | Alarm:{mq135_al}")
    print(f"MQ136(H2S):{mq136_ppm:>6.1f}PPM | Alarm:{mq136_al}")
    print(f"MQ7(CO):{mq7_ppm:>6.1f}PPM | Alarm:{mq7_al}")
    print("="*50 + "\n")

    time.sleep(3)"""
import time
import dht
import math
from machine import Pin, ADC

# ===================== 软件串口（驱动ESP-01，彻底解决AF报错） =====================
class SoftwareSerial:
    def __init__(self, tx_pin, rx_pin, baudrate=115200):
        self.tx = Pin(tx_pin, Pin.OUT)
        self.rx = Pin(rx_pin, Pin.IN)
        self.tx.value(1)
        self.bit_delay = 1000000 // baudrate
    
    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        for byte in data:
            self.tx.value(0)
            time.sleep_us(self.bit_delay)
            for i in range(8):
                self.tx.value((byte >> i) & 1)
                time.sleep_us(self.bit_delay)
            self.tx.value(1)
            time.sleep_us(self.bit_delay)
    
    def read(self, size=128, timeout=1000):
        res = b""
        start = time.ticks_ms()
        while len(res) < size and time.ticks_ms() - start < timeout:
            if self.rx.value() == 0:
                time.sleep_us(self.bit_delay//2)
                byte = 0
                for i in range(8):
                    time.sleep_us(self.bit_delay)
                    byte |= (self.rx.value() << i)
                time.sleep_us(self.bit_delay)
                res += bytes([byte])
        return res

# ===================== 引脚定义 =====================
# DHT22
dht_sensor = dht.DHT22(Pin("P0_28"))

# 超声波
trig = Pin("P0_29", Pin.OUT)
echo = Pin("P1_23", Pin.IN)

# MQ气体传感器
mq135_ao = ADC(Pin("P4_12"))
mq135_do = Pin("P0_30", Pin.IN)
mq136_ao = ADC(Pin("P4_13"))
mq136_do = Pin("P1_21", Pin.IN)
mq7_ao = ADC(Pin("P0_14"))
mq7_do = Pin("P1_2", Pin.IN)

# ===================== ESP-01 软件串口（普通GPIO，无AF报错） =====================
# 任意普通GPIO即可，彻底解决硬件报错
wifi_uart = SoftwareSerial( tx_pin=Pin("P1_17"), rx_pin=Pin("P1_16"), baudrate=115200)

# ===================== WiFi配置（修改这里！） =====================
WIFI_SSID = "Qiaosheng"
WIFI_PWD = "35051049"
TCP_SERVER_IP = "192.168.43.4"
TCP_SERVER_PORT = 8080
wifi_connected = False

# ===================== DHT22参数 =====================
TEMP_OFFSET = -3.2
ALPHA_TEMP = 0.2
ALPHA_HUMI = 0.3
ewma_temp = None
ewma_humi = None

# ===================== MQ传感器参数 =====================
R0_135 = 150.0
R0_136 = 200.0
R0_7   = 60.0
RL = 10.0

A_135, B_135 = 116.6, -2.77
A_136, B_136 = 73.5, -1.82
A_7, B_7 = 99.05, -1.51

ALARM_135 = 300
ALARM_136 = 20
ALARM_7   = 50

# ===================== 工具函数 =====================
def safe_read_dht():
    for _ in range(3):
        try:
            dht_sensor.measure()
            t = dht_sensor.temperature()
            h = dht_sensor.humidity()
            if -40 < t < 80 and 0 < h < 100:
                return t, h
        except:
            time.sleep(0.5)
    return None, None

def read_gas(adc_pin):
    adc_val = adc_pin.read_u16()
    voltage = (adc_val / 65535) * 3.3
    return round(voltage, 2)

def voltage_to_ppm(voltage, R0, a, b):
    if voltage < 0.01:
        return 0.0
    Rs = RL * (3.3 - voltage) / voltage
    ratio = Rs / R0
    return max(0.0, min(10000.0, a * math.pow(ratio, b)))

def read_ultrasonic():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    timeout = 100000
    start = time.ticks_us()
    while echo.value() == 0 and (time.ticks_us() - start) < timeout:
        pass
    if echo.value() == 0:
        return 0.0

    echo_start = time.ticks_us()
    while echo.value() == 1 and (time.ticks_us() - echo_start) < timeout:
        pass
    if echo.value() == 1:
        return 0.0

    dist = (time.ticks_us() - echo_start) * 0.0343 / 2
    return round(dist, 1) if 2 < dist < 400 else 0.0

# ===================== WiFi函数 =====================
def wifi_send_at(cmd, timeout=1000):
    wifi_uart.write(cmd + "\r\n")
    time.sleep_ms(50)
    resp = wifi_uart.read(timeout=timeout)
    return resp.decode('utf-8', 'ignore') if resp else ""

def esp01_init():
    global wifi_connected
    print("=== Initializing ESP-01 ===")
    wifi_send_at("AT+RST")
    time.sleep(2)
    wifi_send_at("AT")
    wifi_send_at("AT+CWMODE=1")
    time.sleep_ms(500)

    print(f"Connecting WiFi: {WIFI_SSID}")
    resp = wifi_send_at(f'AT+CWJAP="{WIFI_SSID}","{WIFI_PWD}"', 5000)
    if "WIFI CONNECTED" in resp or "OK" in resp:
        print("WiFi Connected OK")
        wifi_connected = True
    else:
        print("WiFi Connect Failed")
        return False

    time.sleep(1)
    resp = wifi_send_at(f'AT+CIPSTART="TCP","{TCP_SERVER_IP}",{TCP_SERVER_PORT}', 3000)
    if "CONNECT" in resp:
        print("TCP Connected OK")
        return True
    else:
        print("TCP Connect Failed")
        return False

def send_data_to_wifi(data):
    global wifi_connected
    if not wifi_connected:
        esp01_init()
        return
    try:
        wifi_uart.write(f'AT+CIPSEND={len(data)}\r\n')
        time.sleep_ms(50)
        wifi_uart.write(data)
        print("Data Send OK via WiFi")
    except:
        print("Send Failed, Reconnecting...")
        wifi_connected = False

# ===================== 初始化 =====================
print("="*50)
print("FRDM-MCXN947 Multi-Sensor System")
print("="*50)
esp01_init()
time.sleep(2)

# ===================== 主循环 =====================
while True:
    # 读取温湿度
    raw_t, raw_h = safe_read_dht()
    if raw_t is not None and raw_h is not None:
        cor_t = raw_t + TEMP_OFFSET
        if ewma_temp is None:
            ewma_temp = cor_t
            ewma_humi = raw_h
        else:
            ewma_temp = ALPHA_TEMP * cor_t + (1-ALPHA_TEMP) * ewma_temp
            ewma_humi = ALPHA_HUMI * raw_h + (1-ALPHA_HUMI) * ewma_humi
        temp = round(ewma_temp, 1)
        humi = round(ewma_humi, 1)
    else:
        temp, humi = 0.0, 0.0

    # 读取距离
    dist = read_ultrasonic()

    # 读取气体数据
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    
    mq135_ppm = voltage_to_ppm(mq135_v, R0_135, A_135, B_135)
    mq136_ppm = voltage_to_ppm(mq136_v, R0_136, A_136, B_136)
    mq7_ppm = voltage_to_ppm(mq7_v, R0_7, A_7, B_7)
    
    mq135_al = 1 if mq135_ppm > ALARM_135 else 0
    mq136_al = 1 if mq136_ppm > ALARM_136 else 0
    mq7_al = 1 if mq7_ppm > ALARM_7 else 0

    # 发送数据
    send_data = f"T:{temp}C|H:{humi}%|D:{dist}cm|MQ135:{mq135_ppm:.1f}|MQ136:{mq136_ppm:.1f}|MQ7:{mq7_ppm:.1f}"
    send_data_to_wifi(send_data)

    # 串口打印
    print("="*50)
    print(f"Temp:{temp:>5.1f}C | Humid:{humi:>5.1f}% | Dist:{dist:>5.1f}cm")
    print(f"MQ135(Air):{mq135_ppm:>6.1f}PPM | Alarm:{mq135_al}")
    print(f"MQ136(H2S):{mq136_ppm:>6.1f}PPM | Alarm:{mq136_al}")
    print(f"MQ7(CO):{mq7_ppm:>6.1f}PPM | Alarm:{mq7_al}")
    print("="*50 + "\n")

    time.sleep(3)