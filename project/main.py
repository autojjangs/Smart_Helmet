# coding: utf-8
from micropython import const
from machine import Pin
import bluetooth
import struct
import time


DEVICE_NAME = "SmartHelmet-Vibe"
SERVICE_UUID = bluetooth.UUID("")
COMMAND_CHARACTERISTIC_UUID = bluetooth.UUID("")
#송신파트의 UUID와 일치시킬 것, 현재는 비워뒀습니다.

# 진동 모듈 IN 핀에 연결한 실제 ESP32-C3 GPIO 번호로 수정 필요, 현재는 None으로 설정되어 있습니다.
VIBE_IN_PIN = None
# Smart_Helmet 프로젝트는 진동 시작/종료 명령으로 1, 0만 전송합니다.
ON_COMMAND = "1"
OFF_COMMAND = "0"
# BLE 이벤트 상수/BLE에서 발생하는 이벤트를 구분하기 위한 값입니다.
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
# BLE 광고 데이터 유형 상수
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID128_COMPLETE = const(0x07)
_ADV_FLAG_GENERAL_DISC = const(0x02)
_ADV_FLAG_NO_BREDR = const(0x04)

# BLE 광고 데이터 생성 함수/이 함수는 ESP32-C3가 주변 장치에게 자신을 알리는 BLE 광고 데이터를 만듭니다.
def advertising_payload(name=None, services=None):
    payload = bytearray()
    # BLE 광고 데이터는 길이-타입-값 형식으로 구성됩니다.
    def append(adv_type, value):
        payload.extend(struct.pack("BB", len(value) + 1, adv_type))
        payload.extend(value)
    # 일반적으로 BLE 장치는 범용 발견 가능 및 BR/EDR 미지원 플래그를 포함해야 합니다.
    append(_ADV_TYPE_FLAGS, struct.pack("B", _ADV_FLAG_GENERAL_DISC | _ADV_FLAG_NO_BREDR))
    # 장치 이름과 서비스 UUID를 광고 데이터에 포함할 수 있습니다.
    if name:
        append(_ADV_TYPE_NAME, name.encode("utf-8"))
    # 128비트 서비스 UUID는 완전한 목록으로 광고 데이터에 포함할 수 있습니다.
    if services:
        for uuid in services:
            uuid_bytes = bytes(uuid)
            if len(uuid_bytes) == 16:
                append(_ADV_TYPE_UUID128_COMPLETE, uuid_bytes)
    return payload

# BLE 명령을 정규화하는 함수/BLE로 받은 데이터는 처음에 바이트 형태이며 utf-8로 디코딩하여 문자열로 변환해야 합니다.
def normalize_command(value):
    try:
        command = value.decode("utf-8")
    except UnicodeError:
        command = ""

    return command.strip()

# 진동 BLE 수신기 클래스
class VibrationBleReceiver:
    def __init__(self, pin_no):   
        if pin_no is None:
            raise ValueError("VIBE_IN_PIN을 진동 모듈 IN 핀에 연결한 GPIO 번호로 설정하세요.")

        self._vibe = Pin(pin_no, Pin.OUT, value=0) #진동모듈을 제어할 GPIO 핀을 출력 모드로 설정합니다. value=0이므로 시작할 때는 꺼진 상태입니다.
        self._ble = bluetooth.BLE()
        self._ble.active(True) #BLE 기능을 켜고, BLE 이벤트가 발생하면 _irq() 함수가 호출되도록 등록합니다.
        self._ble.irq(self._irq)
        self._conn_handle = None

        command_characteristic = (
            COMMAND_CHARACTERISTIC_UUID,
            bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE,
        )
        service = (SERVICE_UUID, (command_characteristic,))
        ((self._command_handle,),) = self._ble.gatts_register_services((service,))
    #코드 안에서 만들어지는 BLE 광고 데이터
        self._adv_data = advertising_payload(services=[SERVICE_UUID]) #adv_data → 서비스 UUID 포함
        self._resp_data = advertising_payload(name=DEVICE_NAME) #resp_data → 장치 이름 포함
    # BLE 광고 시작 및 초기 상태 설정
    def start(self):
        self.stop_vibration()
        self._advertise()
        print("=== SmartHelmet ESP32-C3 진동 BLE 수신기 ===")
        print("[BLE] 장치 이름:", DEVICE_NAME)
        print("[BLE] 연결 대기 중...")
    # 진동 제어 메서드
    def start_vibration(self):
        self._vibe.value(1)
        print("[진동] 켜짐")
    # 진동 끄기 메서드
    def stop_vibration(self):
        self._vibe.value(0)
        print("[진동] 꺼짐")
    # BLE 광고 시작 메서드
    def _advertise(self):
        try:
            self._ble.gap_advertise(100000, adv_data=self._adv_data, resp_data=self._resp_data)
        except TypeError:
            # 일부 오래된 MicroPython 빌드는 스캔 응답 데이터를 지원하지 않을 수 있습니다.
            self._ble.gap_advertise(
                100000,
                adv_data=advertising_payload(name="Vibe", services=[SERVICE_UUID]),
            )
    # BLE 이벤트 처리 메서드
    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self._conn_handle, _, _ = data
            print("[BLE] 연결됨")

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                self._conn_handle = None
            self.stop_vibration()
            print("[BLE] 연결 끊김")
            self._advertise()
            print("[BLE] 연결 대기 재시작")

        elif event == _IRQ_GATTS_WRITE:
            _, attr_handle = data
            if attr_handle != self._command_handle:
                return

            command = normalize_command(self._ble.gatts_read(self._command_handle))
            print("[BLE] 수신 명령:", command)

            if command == ON_COMMAND:
                self.start_vibration()
            elif command == OFF_COMMAND:
                self.stop_vibration()
            else:
                print("[BLE] 알 수 없는 명령")
    #진동 핀 초기화
    #BLE 활성화
    #GATT 서비스 등록
    #BLE 광고 시작
    #연결/해제 이벤트 처리
    #명령 수신 시 진동 ON/OFF 처리


# 메인 함수
def main():
    receiver = VibrationBleReceiver(VIBE_IN_PIN)
    receiver.start()

    try:
        while True:
            time.sleep_ms(1000)
    except KeyboardInterrupt:
        receiver.stop_vibration()
        print("중지됨")

# 프로그램 진입점
if __name__ == "__main__":
    main()
