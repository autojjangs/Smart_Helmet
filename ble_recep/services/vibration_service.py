# coding: utf-8
# 역할: 진동 모듈이 연결된 GPIO 핀을 제어합니다.
from machine import Pin


class VibrationService:
    def __init__(self, pin_no):
        if pin_no is None:
            raise ValueError("VIBE_IN_PIN을 진동 모듈 IN 핀에 연결한 GPIO 번호로 설정하세요.")

        self._vibe = Pin(pin_no, Pin.OUT, value=0)

    def start(self):
        self._vibe.value(1)
        print("[진동] 켜짐")

    def stop(self):
        self._vibe.value(0)
        print("[진동] 꺼짐")
