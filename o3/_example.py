# FRDM-MCXN947 最终版（严格匹配官方引脚图）
# 适配：DHT22 / HC-SR04 / MQ传感器 / SG90舵机 / ESP-01
import time
import dht
from machine import Pin, ADC, PWM, UART

# ===================== 引脚定义（100%匹配你的引脚图） =====================
# DHT22 温湿度 (ARD_D8 = P0_28)
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04 超声波
trig = Pin("P0_29", Pin.OUT)  # ARD_D2 = P0_29
echo = Pin("P1_23", Pin.IN)   # ARD_D3 = P1_23

# MQ气体传感器 (ADC + 数字口)
mq135_ao = ADC(Pin("P4_12"))  # ARD_A0 = P4_12
mq135_do = Pin("P0_30", Pin.IN)# ARD_D4 = P0_30
mq136_ao = ADC(Pin("P4_13"))  # ARD_A1 兼容引脚（实测稳定）
mq136_do = Pin("P1_21", Pin.IN)# ARD_D5 = P1_21
mq7_ao = ADC(Pin("P0_14"))    # ARD_A2 = P0_14
mq7_do = Pin("P1_2", Pin.IN)  # ARD_D6 = P1_2

# SG90舵机 (PWM 50Hz, ARD_D7 = P0_31)
#servo = PWM(Pin("P0_10"), freq=10)

#ESP-01 WiFi (UART1，避免占用USB打印串口)
#TX=ARD_D9=P0_10, RX=ARD_D10=P0_27
# ESP-01 使用 UART0 (LPUART0)
#wifi = UART(1, baudrate=115200, tx=Pin("P0_10"), rx=Pin("P0_27"))

# ===================== 功能函数（修复+适配） =====================
# 舵机角度控制 (0-180°)
def servo_angle(angle):
    angle = max(0, min(180, angle))
    # 16位duty换算：0°=1638，180°=8192
    duty = int(1638 + (angle / 180) * (8192 - 1638))
    servo.duty(duty)  # 仅用duty()，无冲突'''

# 超声波测距（防卡死+超时）
def read_ultrasonic():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    # 超时保护（避免死循环）
    timeout = 100000  # 100ms超时
    start = time.ticks_us()
    
    # 等待Echo高电平
    while echo.value() == 0 and time.ticks_us() - start < timeout:
        pass
    if echo.value() == 0:
        return 0.0  # 超时返回0
    
    # 记录高电平开始时间
    echo_start = time.ticks_us()
    # 等待Echo低电平
    while echo.value() == 1 and time.ticks_us() - echo_start < timeout:
        pass
    if echo.value() == 1:
        return 0.0  # 超时返回0
    
    # 计算距离 (声速343m/s = 0.0343cm/us)
    echo_duration = time.ticks_us() - echo_start
    distance = (echo_duration * 0.0343) / 2
    return round(distance, 1) if 2 < distance < 400 else 0.0

# 读取气体传感器模拟值（换算为0-3.3V）
def read_gas(adc_pin):
    # ADC是16位，最大值65535，对应3.3V
    adc_value = adc_pin.read_u16()
    voltage = (adc_value / 65535) * 3.3
    return round(voltage, 2)

# ===================== 初始化 =====================
print("FRDM-MCXN947 System Started")
#servo_angle(90)  # 舵机归中
time.sleep(1)
print("Servo Init Done")
print("MQ Sensor Preheating...\n")

# ===================== 主循环 =====================
while True:
    # 1. 读取DHT22温湿度
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        humi = dht_sensor.humidity()
    except Exception as e:
        temp = 0.0
        humi = 0.0
        print(f"DHT22 Read Fail: {e}")

    # 2. 读取超声波距离
    dist = read_ultrasonic()

    # 3. 读取气体传感器
    mq135_v = read_gas(mq135_ao)
    mq136_v = read_gas(mq136_ao)
    mq7_v = read_gas(mq7_ao)
    # 数字口报警状态（0=正常，1=超标）
    mq135_alarm = mq135_do.value()
    mq136_alarm = mq136_do.value()
    mq7_alarm = mq7_do.value()

    # 4. 串口打印输出（纯英文，无乱码）
    print("="*35)
    print(f"Temp: {temp:>5.1f} C | Humidity: {humi:>5.1f} %")
    print(f"Distance: {dist:>5.1f} cm")
    print(f"MQ135: {mq135_v:>4.2f}V (Alarm: {mq135_alarm})")
    print(f"MQ136: {mq136_v:>4.2f}V (Alarm: {mq136_alarm})")
    print(f"MQ7:   {mq7_v:>4.2f}V (Alarm: {mq7_alarm})")
    print("="*35 + "\n")

    # 5. 舵机动作演示
    '''servo_angle(0)
    time.sleep(0.5)
    servo_angle(180)
    time.sleep(0.5)
    servo_angle(90)'''

    # 6. ESP-01发送数据（已注释，避免报错）
    # 已注释初始化，所以这里也注释
    '''
    try:
        data = f"T:{temp},H:{humi},D:{dist},MQ135:{mq135_v},MQ7:{mq7_v}"
        wifi.write((data + "\r\n").encode())
    except:
        print("ESP-01 Disconnected, Skip Send\n")
    '''

    # 7. 采样间隔（DHT22要求≥2秒）
    time.sleep(2)