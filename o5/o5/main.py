import time
import dht
from machine import Pin, ADC, PWM, UART

# ===================== PIN DEFINITIONS (100% Official Pinout) =====================
# DHT22 Temperature & Humidity (ARD_D8 = P0_28)
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04 Ultrasonic Sensor
trig = Pin("P0_29", Pin.OUT)  # ARD_D2 = P0_29
echo = Pin("P1_23", Pin.IN)   # ARD_D3 = P1_23

# MQ Gas Sensors (Analog + Digital Output)
mq135_ao = ADC(Pin("P4_12"))  # ARD_A0 = P4_12
#mq135_do = Pin("P0_30", Pin.IN)# ARD_D4 = P0_30
mq136_ao = ADC(Pin("P4_13"))  # ARD_A1 = P4_13
#mq136_do = Pin("P1_21", Pin.IN)# ARD_D5 = P1_21
mq7_ao = ADC(Pin("P0_14"))    # ARD_A2 = P0_14
#mq7_do = Pin("P1_2", Pin.IN)  # ARD_D6 = P1_2

# SG90 Servo Motor (Standard 50Hz PWM, ARD_D7 = P0_31)
#servo = PWM(Pin("P0_10"))   # 先创建 PWM 对象，不指定任何频率/占空比
#servo.freq(50)              # 再单独设置频率为 50 Hz
# 原第22行附近
# serv = PWM(Pin("P0_10"), freq=50)   # 错误写法
servo = PWM(Pin("P0_10"), freq=50, duty_ns=1_500_000)   # 正确：50Hz，初始 1.5ms (90°)
# ===================== HC-05 BLUETOOTH MODULE =====================
# UART1 (Does not conflict with USB debug serial port)
# Default: 9600 baud, 8 data bits, no parity, 1 stop bit
"""bluetooth = UART(1, baudrate=9600, tx=Pin("P1_17"), rx=Pin("P1_16"), 
                 bits=8, parity=None, stop=1)"""
# 将蓝牙模块连接到 J8-9(P0_12) 和 J8-12(P0_13)
# TX of HC-05 -> P0_12 (J8-9)
# RX of HC-05 -> P0_13 (J8-12)
# 在初始化蓝牙之前
try:
    bluetooth = UART(1)
    bluetooth.deinit()
    print("UART1 已释放。")
except Exception as e:
    print(f"释放 UART1 时出错: {e}")

# 再用新参数重新初始化
tx_pin = Pin(Pin.board.TX)
rx_pin = Pin(Pin.board.RX)
bluetooth= UART(2, baudrate=9600, rx=rx_pin, tx=tx_pin, timeout=100)

# ===================== FUNCTION DEFINITIONS =====================
# Servo angle control (0-180 degrees)
"""def servo_angle(angle):
    angle = max(0, min(180, angle))
    # 16-bit PWM duty cycle: 0°=1638, 90°=4915, 180°=8192
    duty = int(1638 + (angle / 180) * (8192 - 1638))
    servo.duty(duty)"""
def servo_angle(angle):
    angle = max(0, min(180, angle))
    # 0° → 0.5ms (500_000 ns) , 180° → 2.5ms (2_500_000 ns)
    pulse_ns = int(500_000 + (angle / 180) * 2_000_000)
    servo.duty_ns(pulse_ns)

# Ultrasonic distance measurement (with timeout protection)
def read_ultrasonic():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    timeout = 100000  # 100ms timeout to prevent infinite loop
    start = time.ticks_us()
    
    # Wait for echo high
    while echo.value() == 0 and time.ticks_us() - start < timeout:
        pass
    if echo.value() == 0:
        return 0.0  # Timeout
    
    echo_start = time.ticks_us()
    # Wait for echo low
    while echo.value() == 1 and time.ticks_us() - echo_start < timeout:
        pass
    if echo.value() == 1:
        return 0.0  # Timeout
    
    # Calculate distance (Speed of sound = 343 m/s = 0.0343 cm/us)
    echo_duration = time.ticks_us() - echo_start
    distance = (echo_duration * 0.0343) / 2
    return round(distance, 1) if 2 < distance < 400 else 0.0

# Read gas sensor voltage (0-3.3V)
def read_gas(adc_pin):
    adc_value = adc_pin.read_u16()
    voltage = (adc_value / 65535) * 3.3
    return round(voltage, 2)

# Send data via Bluetooth
def bluetooth_send(data):
    try:
        bluetooth.write((data + "\r\n").encode())
    except:
        pass

# Receive Bluetooth commands (control servo: send 0/90/180)
def bluetooth_receive():
    if bluetooth.any():
        cmd = bluetooth.readline().decode().strip()
        if cmd.isdigit():
            angle = int(cmd)
            servo_angle(angle)
            ack = f"[Bluetooth] Servo rotated to {angle} degrees"
            print(ack)
            bluetooth_send(ack)

# ===================== SYSTEM INITIALIZATION =====================
print("="*50)
print("FRDM-MCXN947 Multi-Sensor System with HC-05 Bluetooth")
print("="*50)
servo_angle(90)  # Center servo on startup
time.sleep(1)
bluetooth_send("[System] Bluetooth connected. Device started.")
print("Servo initialized | Bluetooth initialized")
print("MQ sensors warming up...\n")

# ===================== MAIN LOOP =====================
while True:
    # 1. Read DHT22 temperature and humidity
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        humi = dht_sensor.humidity()
    except Exception as e:
        temp = 0.0
        humi = 0.0
        print(f"DHT22 Read Error: {e}")

    # 2. Read ultrasonic distance
    dist = read_ultrasonic()

    # 3. Read gas sensors
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    #mq135_alarm = mq135_do.value()
    #mq136_alarm = mq136_do.value()
    #mq7_alarm = mq7_do.value()"""

    # 4. Print to serial monitor (computer debug)
    print("="*35)
    print(f"Temp: {temp:>5.1f} °C | Humidity: {humi:>5.1f} %")
    print(f"Distance: {dist:>5.1f} cm")
    print(f"AIE QUAILITY: {mq135_v:>4.2f}") #V (Alarm: {mq135_alarm})")
    print(f"H2S: {mq136_v:>4.2f}")#V (Alarm: {mq136_alarm})")
    print(f"CO:   {mq7_v:>4.2f}")#V (Alarm: {mq7_alarm})")
    print("="*35 + "\n")

    # 5. Send all sensor data via Bluetooth
    data_str = f"Temp:{temp:.1f}C Hum:{humi:.1f}% Dist:{dist:.1f}cm | AIR:{mq135_v}V CO:{mq7_v}V H2S:{mq136_v}V"
    bluetooth_send(data_str)

    # 6. Process Bluetooth commands
    bluetooth_receive()

    # 7. Sampling interval (DHT22 requires ≥2 seconds)
    time.sleep(2)