# coding: utf-8
# 역할: BLE 광고, 연결 상태, GATT 명령 수신을 처리하고 진동 서비스에 동작을 전달합니다.
from micropython import const
import bluetooth
import struct

from config import (
    COMMAND_CHARACTERISTIC_UUID,
    DEVICE_NAME,
    IRQ_CENTRAL_CONNECT,
    IRQ_CENTRAL_DISCONNECT,
    IRQ_GATTS_WRITE,
    OFF_COMMAND,
    ON_COMMAND,
    SERVICE_UUID,
)
from services.vibration_service import VibrationService


_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID128_COMPLETE = const(0x07)
_ADV_FLAG_GENERAL_DISC = const(0x02)
_ADV_FLAG_NO_BREDR = const(0x04)


def advertising_payload(name=None, services=None):
    payload = bytearray()

    def append(adv_type, value):
        payload.extend(struct.pack("BB", len(value) + 1, adv_type))
        payload.extend(value)

    append(_ADV_TYPE_FLAGS, struct.pack("B", _ADV_FLAG_GENERAL_DISC | _ADV_FLAG_NO_BREDR))

    if name:
        append(_ADV_TYPE_NAME, name.encode("utf-8"))

    if services:
        for uuid in services:
            uuid_bytes = bytes(uuid)
            if len(uuid_bytes) == 16:
                append(_ADV_TYPE_UUID128_COMPLETE, uuid_bytes)

    return payload


def normalize_command(value):
    try:
        command = value.decode("utf-8")
    except UnicodeError:
        command = ""

    return command.strip()


class VibrationBleReceiver:
    def __init__(self, pin_no):
        self._vibration = VibrationService(pin_no)
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._conn_handle = None

        command_characteristic = (
            COMMAND_CHARACTERISTIC_UUID,
            bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE,
        )
        service = (SERVICE_UUID, (command_characteristic,))
        ((self._command_handle,),) = self._ble.gatts_register_services((service,))

        self._adv_data = advertising_payload(services=[SERVICE_UUID])
        self._resp_data = advertising_payload(name=DEVICE_NAME)

    def start(self):
        self.stop_vibration()
        self._advertise()
        print("=== SmartHelmet ESP32-C3 진동 BLE 수신기 ===")
        print("[BLE] 장치 이름:", DEVICE_NAME)
        print("[BLE] 연결 대기 중...")

    def start_vibration(self):
        self._vibration.start()

    def stop_vibration(self):
        self._vibration.stop()

    def _advertise(self):
        try:
            self._ble.gap_advertise(100000, adv_data=self._adv_data, resp_data=self._resp_data)
        except TypeError:
            # 일부 오래된 MicroPython 빌드는 스캔 응답 데이터를 지원하지 않을 수 있습니다.
            self._ble.gap_advertise(
                100000,
                adv_data=advertising_payload(name="Vibe", services=[SERVICE_UUID]),
            )

    def _irq(self, event, data):
        if event == IRQ_CENTRAL_CONNECT:
            self._conn_handle, _, _ = data
            print("[BLE] 연결됨")

        elif event == IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                self._conn_handle = None

            self.stop_vibration()
            print("[BLE] 연결 끊김")
            self._advertise()
            print("[BLE] 연결 대기 재시작")

        elif event == IRQ_GATTS_WRITE:
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
