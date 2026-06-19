# FRDM-MCXN947 Full Version
# Compatible: DHT22 / HC-SR04 / MQ Sensors / SG90 Servo / ESP-01
# DHT22 Self-heating Correction + Servo Angle Control
import time
import dht
from machine import Pin, ADC, PWM, UART

# ===================== Pin Definition (100% Match Official Diagram) =====================
# DHT22 Temperature & Humidity (ARD_D8 = P0_28)
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04 Ultrasonic Sensor
trig = Pin("P0_29", Pin.OUT)  # ARD_D2 = P0_29
echo = Pin("P1_23", Pin.IN)   # ARD_D3 = P1_23

# MQ Gas Sensors (ADC + Digital)
mq135_ao = ADC(Pin("P4_12"))  # ARD_A0 = P4_12
mq135_do = Pin("P0_30", Pin.IN)# ARD_D4 = P0_30
mq136_ao = ADC(Pin("P4_13"))  # ARD_A1
mq136_do = Pin("P1_21", Pin.IN)# ARD_D5 = P1_21
mq7_ao = ADC(Pin("P0_14"))    # ARD_A2 = P0_14
mq7_do = Pin("P1_2", Pin.IN)  # ARD_D6 = P1_2

# SG90 Servo (PWM 50Hz, ARD_D7 = P0_31)
servo = PWM(Pin("P0_27"), freq=50)

# ESP-01 WiFi (Commented to avoid errors)
# wifi = UART(1, baudrate=115200, tx=Pin("P0_10"), rx=Pin("P0_27"))

# ===================== DHT22 Self-heating Correction & Filter =====================
TEMP_OFFSET = -3.2  # Calibrate this value based on your actual environment

# EWMA Filter Parameters
ALPHA_TEMP = 0.2
ALPHA_HUMI = 0.3
ewma_temp = None
ewma_humi = None

def safe_read_dht():
    """Read DHT22 safely, retry 3 times"""
    for i in range(3):
        try:
            dht_sensor.measure()
            temp = dht_sensor.temperature()
            humi = dht_sensor.humidity()
            if -40 < temp < 80 and 0 < humi < 100:
                return temp, humi
        except:
            time.sleep(0.5)
    return None, None

def ewma_filter(new_value, last_ewma, alpha):
    """EWMA filter for smooth data"""
    if last_ewma is None:
        return new_value
    return alpha * new_value + (1 - alpha) * last_ewma

# ===================== Servo Control Function (0-180°) =====================
def servo_angle(angle):
    angle = max(0, min(180, angle))
    duty = int(1638 + (angle / 180) * (8192 - 1638))
    servo.duty(duty)

# ===================== Ultrasonic Distance Reading =====================
def read_ultrasonic():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    timeout = 100000
    start = time.ticks_us()
    while echo.value() == 0 and time.ticks_us() - start < timeout:
        pass
    if echo.value() == 0:
        return 0.0
    
    echo_start = time.ticks_us()
    while echo.value() == 1 and time.ticks_us() - echo_start < timeout:
        pass
    if echo.value() == 1:
        return 0.0
    
    echo_duration = time.ticks_us() - echo_start
    distance = (echo_duration * 0.0343) / 2
    return round(distance, 1) if 2 < distance < 400 else 0.0

# ===================== Gas Sensor Reading =====================
def read_gas(adc_pin):
    adc_value = adc_pin.read_u16()
    voltage = (adc_value / 65535) * 3.3
    return round(voltage, 2)

# ===================== Initialization =====================
print("="*45)
print("FRDM-MCXN947 System Started")
print("DHT22 Self-Heating Correction Enabled | SG90 Servo Initialized")
servo_angle(90)  # Servo center at 90°
time.sleep(2)
print("System Initialization Complete, Starting Data Acquisition...")
print("="*45 + "\n")

# ===================== Main Loop =====================
while True:
    # 1. Read Temperature & Humidity
    raw_temp, raw_humi = safe_read_dht()
    if raw_temp is not None:
        corrected_temp = raw_temp + TEMP_OFFSET
        filtered_temp = ewma_filter(corrected_temp, ewma_temp, ALPHA_TEMP)
        filtered_humi = ewma_filter(raw_humi, ewma_humi, ALPHA_HUMI)
        ewma_temp, ewma_humi = filtered_temp, filtered_humi
        temp = round(filtered_temp, 1)
        humi = round(filtered_humi, 1)
    else:
        temp, humi = 0.0, 0.0
        print("DHT22 Read Failed!")

    # 2. Read Distance & Gas Sensors
    dist = read_ultrasonic()
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    mq135_alarm = mq135_do.value()
    mq136_alarm = mq136_do.value()
    mq7_alarm = mq7_do.value()

    # 3. Serial Print (English Only)
    print(f"Raw Temp:{raw_temp:>4.1f}°C | Corrected:{temp:>4.1f}°C | Humidity:{humi:>4.1f}%")
    print(f"Distance:{dist:>4.1f}cm | MQ135:{mq135_v:>4.2f}V | MQ136:{mq136_v:>4.2f}V | MQ7:{mq7_v:>4.2f}V")
    print("-"*45)

    # 4. SG90 Servo Demo (0°→180°→90° Loop)
    servo_angle(0)
    time.sleep(0.6)
    servo_angle(180)
    time.sleep(0.6)
    servo_angle(90)
    time.sleep(0.8)

    # 5. Sampling Interval
    time.sleep(1)