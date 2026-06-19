# FRDM-MCXN947 完整版
# 适配：DHT22 / HC-SR04 / MQ传感器 / SG90舵机 / ESP-01
# DHT22自发热修正 + 舵机角度控制
import time
import dht
from machine import Pin, ADC, PWM, UART

# ===================== 引脚定义（100%匹配官方引脚图） =====================
# DHT22 温湿度 (ARD_D8 = P0_28)
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04 超声波
trig = Pin("P0_29", Pin.OUT)  # ARD_D2 = P0_29
echo = Pin("P1_23", Pin.IN)   # ARD_D3 = P1_23

# MQ气体传感器 (ADC + 数字口)
mq135_ao = ADC(Pin("P4_12"))  # ARD_A0 = P4_12
mq135_do = Pin("P0_30", Pin.IN)# ARD_D4 = P0_30
mq136_ao = ADC(Pin("P4_13"))  # ARD_A1
mq136_do = Pin("P1_21", Pin.IN)# ARD_D5 = P1_21
mq7_ao = ADC(Pin("P0_14"))    # ARD_A2 = P0_14
mq7_do = Pin("P1_2", Pin.IN)  # ARD_D6 = P1_2

# SG90舵机 (PWM 50Hz, ARD_D7 = P0_31) ✅ 已启用
servo = PWM(Pin("P0_31"), freq=50)

# ESP-01 WiFi (注释，避免报错)
# wifi = UART(1, baudrate=115200, tx=Pin("P0_10"), rx=Pin("P0_27"))

# ===================== DHT22 自发热修正与滤波算法 =====================
TEMP_OFFSET = -3.2  # 温度校准偏移量（根据实际室温修改）

# 指数加权滤波参数
ALPHA_TEMP = 0.2
ALPHA_HUMI = 0.3
ewma_temp = None
ewma_humi = None

def safe_read_dht():
    """安全读取DHT22，重试3次"""
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
    """指数滤波，数据更平滑"""
    if last_ewma is None:
        return new_value
    return alpha * new_value + (1 - alpha) * last_ewma

# ===================== 舵机角度控制函数（0-180°） =====================
def servo_angle(angle):
    # 限制角度在0~180°之间
    angle = max(0, min(180, angle))
    # 16位PWM占空比换算：0°=1638，180°=8192
    duty = int(1638 + (angle / 180) * (8192 - 1638))
    servo.duty(duty)

# ===================== 超声波测距函数 =====================
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

# ===================== 气体传感器读取函数 =====================
def read_gas(adc_pin):
    adc_value = adc_pin.read_u16()
    voltage = (adc_value / 65535) * 3.3
    return round(voltage, 2)

# ===================== 初始化 =====================
print("="*45)
print("FRDM-MCXN947 系统启动")
print("DHT22自发热修正已启用 | SG90舵机已初始化")
servo_angle(90)  # 舵机开机归中（90°）
time.sleep(2)
print("系统初始化完成，开始采集数据...")
print("="*45 + "\n")

# ===================== 主循环 =====================
while True:
    # 1. 读取温湿度（滤波+修正）
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
        print("DHT22读取失败！")

    # 2. 读取距离/气体传感器
    dist = read_ultrasonic()
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    mq135_alarm = mq135_do.value()
    mq136_alarm = mq136_do.value()
    mq7_alarm = mq7_do.value()

    # 3. 串口打印所有数据
    print(f"原始温度:{raw_temp:>4.1f}℃ | 校准后:{temp:>4.1f}℃ | 湿度:{humi:>4.1f}%")
    print(f"距离:{dist:>4.1f}cm | MQ135:{mq135_v:>4.2f}V | MQ136:{mq136_v:>4.2f}V | MQ7:{mq7_v:>4.2f}V")
    print("-"*45)

    # 4. SG90舵机演示（0°→180°→90° 循环）
    servo_angle(0)
    time.sleep(0.6)
    servo_angle(180)
    time.sleep(0.6)
    servo_angle(90)
    time.sleep(0.8)

    # 5. 采样间隔（DHT22最低要求）
    time.sleep(1)