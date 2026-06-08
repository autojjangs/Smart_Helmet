"""
GPS 서비스 (gps_service.py)

[작은 변경점]
  - serial / pynmea2 import를 gps_loop() 함수 안으로 옮겼다.
    이유: 테스트 모드(파싱전용/이동시뮬)에서는 GPS 수신을 안 하는데,
          모듈 상단에서 serial/pynmea2를 import하면 그 패키지가 없는 환경(예: 일반 PC)에서는
          navigation/led/ble를 import만 해도 실패한다. 실제 수신을 시작할 때만 import하도록 분리.
  - get_current_location / calculate_distance / get_status 는 순수 로직이라 그대로.
"""

import asyncio
import math
import time


# 최신 GPS 위치를 저장할 전역 변수
_current_lon = None
_current_lat = None
_last_update = None   # 마지막으로 좌표를 받은 시각


async def gps_loop():
    """백그라운드에서 GPS 데이터를 계속 읽어오는 비동기 루프(실제 모드에서만 사용)."""
    global _current_lon, _current_lat

    # 실제 수신을 시작할 때만 import (테스트 모드 보호)
    import serial
    import pynmea2

    try:
        # 라즈베리파이 4 기본 UART 포트 ('/dev/serial0')
        ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)

        while True:
            line = ser.readline().decode('ascii', errors='replace')

            if line.strip():
                print(f"[GPS 데이터] {line.strip()}")

            # NMEA 데이터 중 위치 정보가 담긴 GPGGA 또는 GPRMC 문장만 파싱
            if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                try:
                    msg = pynmea2.parse(line)
                    if hasattr(msg, 'latitude') and msg.latitude != 0.0 and msg.longitude != 0.0:
                        global _last_update
                        _current_lat = msg.latitude
                        _current_lon = msg.longitude
                        _last_update = time.time()
                except pynmea2.ParseError:
                    pass

            # 메인 루프가 블로킹되지 않도록 아주 짧게 대기
            await asyncio.sleep(0.01)

    except Exception as e:
        print(f"[GPS] 모듈 연결 오류: {e}")


def get_current_location():
    """최신 (경도, 위도) 반환. 위성이 안 잡혔으면 (None, None)."""
    return _current_lon, _current_lat


def calculate_distance(lon1, lat1, lon2, lat2):
    """
    [핵심 알고리즘] 하버사인(Haversine) 공식
    두 좌표 간의 실제 직선 거리(m)를 계산한다.
    """
    R = 6371000  # 지구 반지름 (미터)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # 미터 단위 거리


def get_status():
    """웹서버용: 현재 좌표 + 수신 경과 시간."""
    age = None
    if _last_update is not None:
        age = round(time.time() - _last_update, 1)
    return {
        "lon": _current_lon,
        "lat": _current_lat,
        "has_fix": _current_lon is not None and _current_lat is not None,
        "age_seconds": age,
    }