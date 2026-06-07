import serial
import pynmea2
import asyncio
import math
import time


# 최신 GPS 위치를 저장할 전역 변수
_current_lon = None
_current_lat = None
_last_update = None   # ← 추가 (마지막으로 좌표를 받은 시각)

async def gps_loop():
    """백그라운드에서 GPS 데이터를 계속 읽어오는 비동기 루프"""
    global _current_lon, _current_lat
    
    try:
        # 라즈베리파이 4 기본 UART 포트 ('/dev/serial0')
        ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)
        
        while True:
            # 시리얼 통신으로 한 줄씩 읽기
            line = ser.readline().decode('ascii', errors='replace')
            
            if line.strip():
                print(f"[GPS 데이터] {line.strip()}")

            # NMEA 데이터 중 위치 정보가 담긴 GPGGA 또는 GPRMC 문장만 파싱
            if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                try:
                    msg = pynmea2.parse(line)
                    # 위성 신호가 잡혀서 유효한 좌표가 들어왔을 때만 업데이트
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
    """최신 (경도, 위도) 반환. 위성이 안 잡혔으면 None 반환"""
    return _current_lon, _current_lat

def calculate_distance(lon1, lat1, lon2, lat2):
    """
    [핵심 알고리즘] 하버사인(Haversine) 공식
    현재 GPS 위치와 목표 지점 간의 실제 직선 거리(m)를 계산합니다.
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

    return R * c  # 미터 단위 거리 반환

def get_status():
    """웹서버용: 현재 좌표 + 수신 경과 시간을 반환"""
    age = None
    if _last_update is not None:
        age = round(time.time() - _last_update, 1)
    return {
        "lon": _current_lon,
        "lat": _current_lat,
        "has_fix": _current_lon is not None and _current_lat is not None,
        "age_seconds": age,
    }
