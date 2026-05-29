# coding: utf-8
# 역할: ESP32-C3에서 실행되는 진입점입니다. BLE 수신기를 생성하고 계속 동작시킵니다.
import time

from config import VIBE_IN_PIN
from services.ble_receiver import VibrationBleReceiver


def main():
    receiver = VibrationBleReceiver(VIBE_IN_PIN)
    receiver.start()

    try:
        while True:
            time.sleep_ms(1000)
    except KeyboardInterrupt:
        receiver.stop_vibration()
        print("중지됨")


if __name__ == "__main__":
    main()
