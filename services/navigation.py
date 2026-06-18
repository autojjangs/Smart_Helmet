"""
실시간 내비게이션 코어 (navigation.py)

기존 main.py의 async main() 루프를 모듈 함수 run(stop_event)로 옮겨,
helmet_app.py의 내비 스레드에서 호출할 수 있게 한 것이다.

[실행 모드] 환경변수 HELMET_TEST_MODE
  0 = 실제 모드 : GPS 수신 + 실제 LED/BLE (root 필요)
  1 = 파싱 전용 : 고정 출발지로 경로만 파싱·출력 후 종료 (실내/비-root 가능)
  2 = 이동 시뮬 : 가상 위치를 경로 안내 지점 따라 정해진 속도로 전진시켜
                  50m 진동 / 10m 통과 로직까지 검증
"""

import os
import asyncio
import time

from services import tmap_service, gps_service, led_service, ble_service


def _read_mode():
    try:
        return int(os.getenv("HELMET_TEST_MODE", "0"))
    except ValueError:
        return 0


def _read_step():
    try:
        return float(os.getenv("HELMET_SIM_STEP_M", "15"))
    except ValueError:
        return 15.0


class _SimPosition:
    """모드 2용 가상 위치. 목표 지점 쪽으로 step_m(m)씩 직선 전진한다."""

    def __init__(self, start_lon, start_lat, step_m=15.0):
        self.lon = start_lon
        self.lat = start_lat
        self.step_m = step_m

    def update_toward(self, target_lon, target_lat):
        d = gps_service.calculate_distance(self.lon, self.lat, target_lon, target_lat)
        if d <= self.step_m or d == 0:
            self.lon, self.lat = target_lon, target_lat
        else:
            f = self.step_m / d
            self.lat += (target_lat - self.lat) * f
            self.lon += (target_lon - self.lon) * f

    def get(self):
        return self.lon, self.lat


# Live navigation info exposed to the web /status (updated every loop)
_live = {
    "distance_to_next": None,   # meters to the current target guide point
    "next_turn": None,          # turn label, e.g. "좌회전"
    "next_desc": None,          # guidance description text
    "remaining_turns": None,    # number of remaining turn maneuvers
    "remaining_points": None,   # number of remaining guide points
}


def _reset_live():
    for k in _live:
        _live[k] = None


def status():
    """helmet_app.py /status 용 요약 (경로 요약 + 실시간 안내 정보)."""
    return {
        "mode": _read_mode(),
        "route": tmap_service.get_route_summary(),
        "live": dict(_live),
    }


async def run(stop_event):
    """
    내비게이션 메인 코루틴.

    Args:
        stop_event (threading.Event): 외부(웹서버)에서 정지를 요청하면 set() 된다.
    """
    mode = _read_mode()
    step_m = _read_step()

    print(f"=== [NAV] 내비게이션 시작 (mode={mode}) ===")

    _reset_live()  # 새 주행 시작 시 실시간 정보 초기화

    is_vibrating = False
    last_vibrated_index = -1

    # 1) 모드별 하드웨어/출발지 준비
    if mode in (1, 2):
        led_service.init(simulation=False)
        ble_service.set_simulation(True)
        start_lon, start_lat = tmap_service.START_X, tmap_service.START_Y
        print(f"[NAV] 테스트 출발지(고정): ({start_lat}, {start_lon})")
    elif mode == 3:
        print("=== [NAV] 시연 모드 (Mode 3) 영상 동기화 준비 ===")
        # 하드웨어 실제 사용
        led_service.init(simulation=False)
        ble_service.set_simulation(False)
        await ble_service.connect_all()
        print("[NAV] 시연 모드 하드웨어 연결 완료.")

        # 시작 신호 대기 (사용자가 마음의 준비를 할 시간 1초)
        print(">>> [시연] 1초 뒤 초기 신호(양쪽 0.6초 켜짐)가 울립니다. 영상 틀 준비! <<<")
        await asyncio.sleep(1)

        # 시작 신호 (양쪽 동시 ON)
        print("[시연] 초기 신호 ON (영상을 틀 준비를 하세요!)")
        
        # 1. 시각적 신호인 LED를 가장 먼저 즉시 켭니다. (이전에 "right"였던 것을 "all"로 수정)
        led_service.start_led_blink("all")
        
        # 2. BLE 통신은 딜레이가 발생해도 전체 타이머를 막지 않도록 백그라운드(Task)로 던집니다.
        asyncio.create_task(ble_service.start_vibration("left"))
        asyncio.create_task(ble_service.start_vibration("right"))
        
        await asyncio.sleep(0.6) # 이제 어떤 딜레이가 있어도 무조건 칼같이 0.6초만 셉니다.

        # 시작 신호 OFF -> 이때 영상을 딱 재생!
        print("[시연] 초기 신호 OFF. ===== 이 메시지를 보면 영상 재생 시작! =====")
        
        # 1. 시각적 신호 즉시 OFF
        led_service.stop_led()
        
        # 2. 진동 정지 명령도 백그라운드로 던짐
        asyncio.create_task(ble_service.stop_vibration("left"))
        asyncio.create_task(ble_service.stop_vibration("right"))

        # 시연 스케줄 (초 단위, "명령", "방향")
        demo_schedule = [
            (9, "on", "right"),   # 13초 우회전의 50m 전
            (15, "off", "right"), # 10m 전 통과
            (34, "on", "left"),   # 40초 좌회전의 50m 전
            (41, "off", "left"),  # 10m 전 통과
            (49, "on", "right"),  # 53초 우회전의 50m 전
            (55, "off", "right"), # 10m 전 통과
            (67, "on", "left"),   # 1분 11초 좌회전의 50m 전 (1분 7초)
            (73, "off", "left"),  # 10m 전 통과 (1분 10초)
            (74, "on", "right"),  # 1분 18초 우회전의 50m 전 (1분 14초)
            (80, "off", "right"), # 10m 전 통과 (1분 17초)
            (82, "end", "none")   # 영상(1분 20초) 종료 직후 시연 종료
        ]

        # 타이머 시작! (이제 블루투스 지연과 상관없이 정확한 타이밍에 시작됩니다)
        start_time = time.time()
        event_idx = 0

        try:
            while not stop_event.is_set() and event_idx < len(demo_schedule):
                current_time = time.time() - start_time
                scheduled_time, action, direction = demo_schedule[event_idx]

                if current_time >= scheduled_time:
                    if action == "on":
                        print(f"[{current_time:.1f}초] {direction} 방향 50m 전 신호 ON")
                        led_service.start_led_blink(direction)
                        asyncio.create_task(ble_service.start_vibration(direction)) # BLE 비동기 처리
                    
                    elif action == "off":
                        print(f"[{current_time:.1f}초] {direction} 방향 10m 전 신호 OFF")
                        led_service.stop_led()
                        asyncio.create_task(ble_service.stop_vibration(direction))  # BLE 비동기 처리
                        
                    elif action == "end":
                        print(f"[{current_time:.1f}초] 시연용 타임라인 종료!")
                        break
                    
                    event_idx += 1

                await asyncio.sleep(0.05)
                
        except Exception as e:
            print(f"[NAV] 시연 중단 오류: {e}")

        return

    else:
        led_service.init(simulation=False)
        ble_service.set_simulation(False)
        asyncio.create_task(gps_service.gps_loop())

        print("[NAV] GPS 위성 신호를 찾는 중입니다...")
        start_lon, start_lat = None, None
        while start_lon is None:
            if stop_event.is_set():
                print("[NAV] 정지 요청 - GPS 대기 중 종료")
                return
            start_lon, start_lat = gps_service.get_current_location()
            await asyncio.sleep(1)
        print(f"[NAV] 현재 위치 확인 완료! (경도: {start_lon}, 위도: {start_lat})")

    # 2) 경로 탐색(파싱)
    tmap_service.init_route(start_lon, start_lat)
    tmap_service.print_all_guide_points()

    # 모드 1: 파싱 결과만 확인하고 종료
    if mode == 1:
        print("[NAV] (모드 1) 파싱 전용 - 안내 지점 출력 완료, 내비 루프는 실행하지 않고 종료합니다.")
        return

    # 3) BLE 연결 1회 수립
    await ble_service.connect_all()

    sim = _SimPosition(start_lon, start_lat, step_m) if mode == 2 else None

    # 4) 실시간 내비게이션 루프 (2초 주기)
    try:
        while not stop_event.is_set():
            try:
                await asyncio.sleep(2)

                # 4-1) 현재 위치 갱신
                if mode == 2:
                    ti = tmap_service.get_current_info()
                    if ti[0] is not None:
                        sim.update_toward(ti[0], ti[1])
                    current_lon, current_lat = sim.get()
                else:
                    current_lon, current_lat = gps_service.get_current_location()

                # 4-2) 목적지 도착 체크
                summary = tmap_service.get_route_summary()
                if summary and summary["current_index"] >= summary["total_points"]:
                    print("[EVENT] 목적지 도착! 경로 안내를 종료합니다.")
                    await ble_service.stop_vibration("left")
                    await ble_service.stop_vibration("right")
                    led_service.stop_led()
                    # 도착 상태를 웹에 반영
                    _live["distance_to_next"] = 0
                    _live["next_turn"] = "도착"
                    _live["next_desc"] = "목적지 도착"
                    _live["remaining_turns"] = 0
                    _live["remaining_points"] = 0
                    break

                # 4-3) 현재 목표 안내 지점 정보
                target_lon, target_lat, turn_type, current_index = tmap_service.get_current_info()

                # 4-4) 위치 → 목표 지점까지 남은 거리(m)
                real_distance = gps_service.calculate_distance(
                    current_lon, current_lat, target_lon, target_lat
                )
                print(f"[내비게이션] 다음 지점(Index {current_index})까지 남은 거리: {int(real_distance)}m")

                # update live info for the web page
                guide = tmap_service.get_current_guide()
                _live["distance_to_next"] = int(real_distance)
                _live["next_turn"] = tmap_service.get_turn_label(turn_type)
                _live["next_desc"] = guide["description"] if guide else ""
                _live["remaining_turns"] = tmap_service.count_remaining_turns()
                _live["remaining_points"] = max(0, summary["total_points"] - current_index)

                # [1] 지점 통과 판정 (반경 10m 이내)
                if real_distance <= 10:
                    print(f"[EVENT] 안내 지점(Index {current_index}) 통과 - 신호 종료 및 다음 구간 로드")
                    await ble_service.stop_vibration("left")
                    await ble_service.stop_vibration("right")
                    led_service.stop_led()
                    is_vibrating = False
                    tmap_service.advance_to_next()

                # [2] 신호 시작 (10m 초과 ~ 50m 이내)
                elif real_distance <= 50 and not is_vibrating and current_index != last_vibrated_index:
                    direction = "left" if turn_type == 12 else "right"
                    print(f"[EVENT] {int(real_distance)}m 전방 {direction} turn - 진동/LED 시작")
                    await ble_service.start_vibration(direction)
                    led_service.start_led_blink(direction)
                    is_vibrating = True
                    last_vibrated_index = current_index

            except Exception as e:
                print(f"[NAV] 루프 오류: {e}")
                await asyncio.sleep(2)

        if stop_event.is_set():
            print("[NAV] 정지 요청 - 내비 루프 종료")

    finally:
        led_service.stop_led()
        await asyncio.sleep(0)
        await ble_service.disconnect_all()
        _reset_live()
        print("[NAV] 정리 완료")
