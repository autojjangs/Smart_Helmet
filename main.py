import asyncio
from services import ble_service, led_service, tmap_service, gps_service

is_vibrating = False
last_vibrated_index = -1

async def main():
    global is_vibrating, last_vibrated_index
        
    print("=== 스마트 헬멧 시스템 가동 ===")
    
    # 1. GPS 백그라운드 수신 시작
    asyncio.create_task(gps_service.gps_loop())
    
    print("\n[GPS] 위성 신호를 찾는 중입니다. (야외에서 테스트 권장)...")
    current_lon, current_lat = None, None
    while current_lon is None:
        current_lon, current_lat = gps_service.get_current_location()
        await asyncio.sleep(1) # 1초마다 신호 확인
        
    print(f"[GPS] 현재 위치 확인 완료! (경도: {current_lon}, 위도: {current_lat})")
    
    # 2. TMAP 경로 탐색 (최초 1회) - 현재 GPS 위치를 출발지로 넘겨줌
    tmap_service.init_route(current_lon, current_lat)
    tmap_service.print_all_guide_points()
    
    # 3. 실시간 내비게이션 루프 (2초 주기)
    while True:
        try:
            # 2초 대기 (요구사항)
            await asyncio.sleep(2)
            
            # 매 루프마다 최신 내 위치 갱신
            current_lon, current_lat = gps_service.get_current_location()

            # 목적지 도착 체크
            summary = tmap_service.get_route_summary()
            if summary and summary['current_index'] >= summary['total_points']:
                print("[EVENT] 목적지 도착! 경로 안내를 종료합니다.")
                await ble_service.stop_vibration("left")
                await ble_service.stop_vibration("right")
                led_service.stop_led()
                break

            # 현재 목표 안내 지점의 정보(좌표, 회전타입, 인덱스) 가져오기
            target_lon, target_lat, turn_type, current_index = tmap_service.get_current_info()

            # [핵심] 실제 내 위치와 타겟 지점까지의 남은 거리(m) 계산
            real_distance = gps_service.calculate_distance(current_lon, current_lat, target_lon, target_lat)
            print(f"[내비게이션] 다음 지점(Index {current_index})까지 남은 거리: {int(real_distance)}m")

            # 신호 시작 (50m 이내 진입 시)
            if real_distance <= 50 and not is_vibrating:
                if current_index != last_vibrated_index:
                    direction = "left" if turn_type == 12 else "right"
                    print(f"[EVENT] {int(real_distance)}m 전방 {direction} turn - 진동/LED 시작")
                    
                    await ble_service.start_vibration(direction)
                    led_service.start_led_blink(direction)               

                    is_vibrating = True
                    last_vibrated_index = current_index

            # 지점 통과 판정 (안내 지점 반경 10m 이내로 들어오면 통과한 것으로 간주하고 다음으로 이동)
            elif real_distance <= 10:
                print(f"[EVENT] 안내 지점(Index {current_index}) 통과 - 신호 종료 및 다음 구간 로드")
                
                # 양쪽 장갑에 모두 정지 신호를 보냄
                await ble_service.stop_vibration("left")
                await ble_service.stop_vibration("right")
                led_service.stop_led()
                is_vibrating = False
                
                # 수동(Enter)이 아니라 자동으로 다음 지점으로 이동!
                tmap_service.advance_to_next()

        except Exception as e:
            print(f"오류 발생: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())