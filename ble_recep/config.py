# coding: utf-8
# 역할: ESP32-C3 BLE 수신기에서 사용하는 장치명, UUID, GPIO 핀, 명령값을 관리합니다.
from micropython import const
import bluetooth


DEVICE_NAME = "SmartHelmet-Vibe"

# 송신 파트의 UUID와 일치시켜야 합니다.
SERVICE_UUID = bluetooth.UUID("")
COMMAND_CHARACTERISTIC_UUID = bluetooth.UUID("")

# 진동 모듈 IN 핀에 연결한 실제 ESP32-C3 GPIO 번호로 수정하세요.
VIBE_IN_PIN = None

# Smart_Helmet 프로젝트는 진동 시작/종료 명령으로 1, 0만 전송합니다.
ON_COMMAND = "1"
OFF_COMMAND = "0"

# BLE 이벤트 상수
IRQ_CENTRAL_CONNECT = const(1)
IRQ_CENTRAL_DISCONNECT = const(2)
IRQ_GATTS_WRITE = const(3)
