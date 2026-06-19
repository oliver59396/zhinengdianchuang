import time
import dht
from machine import Pin, ADC, PWM, UART
import math

# ===================== PIN DEFINITIONS =====================
# DHT22
dht_sensor = dht.DHT22(Pin("P0_28"))

# HC-SR04
trig = Pin("P0_29", Pin.OUT)
echo = Pin("P1_23", Pin.IN)

# MQ Gas Sensors (Analog)
mq135_ao = ADC(Pin("P4_12"))
mq136_ao = ADC(Pin("P4_13"))
mq7_ao   = ADC(Pin("P0_14"))

# 负载电阻 (通常为 10kΩ，根据实际电路调整)
RL = 10.0   # kΩ
Vref = 3.3  # 参考电压


# MQ135 空气质量 (a, b 取自 MQUnified 库，适用综合空气质量)
MQ135_R0 = 200    # 暂时占位，待实测替换
MQ135_A  = 116.6020682
MQ135_B  = -2.769034857

# MQ136 硫化氢
MQ136_R0 = 3.9
MQ136_A  = 14.67
MQ136_B  = -1.25

# MQ7 一氧化碳
MQ7_R0   = 0.5
MQ7_A    = 99.042
MQ7_B    = -1.518

# ===== 气体浓度转换函数（修正版） =====
def read_gas_ppm(adc_pin, r0, a, b):
    """
    读取 MQ 传感器并返回 ppm
    ppm = a * (Rs/R0)^b
    """
    adc_val = adc_pin.read_u16()
    Vout = (adc_val / 65535) * Vref
    if Vout == 0:
        return 0.0

    # 分压公式：Vout = Vref * RL / (Rs + RL)  => Rs = RL * (Vref - Vout) / Vout
    Rs = RL * (Vref - Vout) / Vout
    ratio = Rs / r0
    if ratio <= 0:
        return 0.0

    ppm = a * math.pow(ratio, b)
    return round(ppm, 1)

def read_gas_voltage(adc_pin):
    """原有的电压读取函数，用于调试"""
    adc_val = adc_pin.read_u16()
    Vout = (adc_val / 65535) * Vref
    return round(Vout, 2)

# ===================== 其他功能函数 (保持不变) =====================
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

def servo_angle(angle):
    angle = max(0, min(180, angle))
    pulse_ns = int(500_000 + (angle / 180) * 2_000_000)
    servo.duty_ns(pulse_ns)

def bluetooth_send(data):
    try:
        bluetooth.write((data + "\r\n").encode())
    except:
        pass

def bluetooth_receive():
    if bluetooth.any():
        cmd = bluetooth.readline().decode().strip()
        if cmd.isdigit():
            angle = int(cmd)
            servo_angle(angle)
            ack = f"[Bluetooth] Servo rotated to {angle} degrees"
            print(ack)
            bluetooth_send(ack)

# ===================== 系统初始化 =====================
print("="*50)
print("FRDM-MCXN947 Multi-Sensor System (Gas Concentrations in ppm)")
print("="*50)
servo_angle(90)
time.sleep(1)
bluetooth_send("[System] Bluetooth connected. Device started.")
print("Servo initialized | Bluetooth initialized")
print("MQ sensors warming up...\n")

# ===================== 可选：自动标定 R0 =====================
def auto_calibrate_r0(adc_pin, a, b, expected_ppm=0):
    """在洁净空气中计算 R0，保持传感器在洁净环境运行 5 分钟后调用"""
    total = 0
    num = 10
    for i in range(num):
        adc_val = adc_pin.read_u16()
        Vout = (adc_val / 65535) * Vref
        Rs = RL * (Vref - Vout) / Vout
        total += Rs
        time.sleep(0.5)
    Rs_avg = total / num
    # 洁净空气中浓度近似 0，但公式无法除 0，通常取 Rs/R0 典型值
    # 例如 MQ135 典型 ratio = 3.6, 则 R0 = Rs_avg / 3.6
    # 这里需要用户根据手册填入典型 ratio
    # 为简化，返回 Rs_avg 作为参考
    return Rs_avg

# ===================== 主循环 =====================
while True:
    # 1. 读取 DHT22
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        humi = dht_sensor.humidity()
    except Exception as e:
        temp = 0.0
        humi = 0.0
        print(f"DHT22 Read Error: {e}")
    
    # 2. 超声波距离
    dist = read_ultrasonic()
    
    # 3. 读取气体浓度 (ppm) 和 电压 (调试备用)
    # MQ135 空气质量 (ppm, 通常以 NH3 或 苯为参考)
    mq135_ppm = read_gas_ppm(mq135_ao, MQ135_R0, MQ135_A, MQ135_B)
    mq136_ppm = read_gas_ppm(mq136_ao, MQ136_R0, MQ136_A, MQ136_B)   # H2S ppm
    mq7_ppm   = read_gas_ppm(mq7_ao,   MQ7_R0,   MQ7_A,   MQ7_B)     # CO ppm
    
    # 可选：同时输出电压用于调试
    mq135_v = read_gas_voltage(mq135_ao)
    mq136_v = read_gas_voltage(mq136_ao)
    mq7_v   = read_gas_voltage(mq7_ao)
    
    # 4. 打印
    print("="*35)
    print(f"Temp: {temp:>5.1f} °C | Humidity: {humi:>5.1f} %")
    print(f"Distance: {dist:>5.1f} cm")
    print(f"AIR QUALITY: {mq135_ppm:>6.1f} ppm  (voltage: {mq135_v} V)")
    print(f"H2S: {mq136_ppm:>6.1f} ppm  (voltage: {mq136_v} V)")
    print(f"CO:  {mq7_ppm:>6.1f} ppm  (voltage: {mq7_v} V)")
    print("="*35 + "\n")
    
    # 5. 蓝牙发送 (可以选择发送 ppm 或同时发送电压)
    data_str = f"Temp:{temp:.1f}C Hum:{humi:.1f}% Dist:{dist:.1f}cm | AIR:{mq135_ppm:.0f}ppm CO:{mq7_ppm:.0f}ppm H2S:{mq136_ppm:.0f}ppm"
    bluetooth_send(data_str)
    
    # 6. 舵机指令处理
    bluetooth_receive()

    
    time.sleep(2)