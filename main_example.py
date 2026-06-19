def uart():
 from machine import Pin
 from machine import UART
 tx_pin = Pin(Pin.board.TX) #-> TX引脚定义
 rx_pin = Pin(Pin.board.RX) #-> RX引脚声明
 #-> 初始化uart
uart = UART(2, baudrate=115200, rx=rx_pin,
tx=tx_pin)
#-> 通过uart发送数据
uart.write("hello")
#-> 读取数据
print(uart.read(10))
#-> 循环读取数据
while(1):
 uart.write(uart.read(1))