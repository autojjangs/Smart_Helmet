import asyncio
from services import ble_service



is_vibrating=False
last_vibrated_index=-1
async def main():
    global is_vibrating, last_vibrated_index
        
    print("=== 스마트 헬멧 시스템 가동 ===")
        
    while True:
        try:
            
            # distance: 남은 거리(우회전까지 100m 남았으면 distance=100으로 표시, Response에 있는 데이터)
            # turn_type: 회전 코드 (12:좌, 13:우)
            # current_index: 현재 안내 지점의 번호, 회전 등을 수행하면 index-=1이 되는점을 통해 종료 신호 전달

            #아직 tmap api에서 데이터 파싱하는 코드 작성이 안됐으므로 원본 response에서 가져오겠다는 구조만 작성함
            #[추후 구현] distance, turn_type, current_index = await tmap_service.get_current_info()
            
            #테스트를 위해 임시로 값 설정. 나중에 지울것
            distance=100; turn_type=13; current_index=9

            #신호 시작
            if distance <= 100 and not is_vibrating:
                if current_index != last_vibrated_index:
                    direction = "left" if turn_type == 12 else "right"
                    print(f"[EVENT] {distance}m 전방 {direction} turn - 진동 시작")
                    
                    await ble_service.start_vibration(direction)
                    #여기에 LED Strip 점등 신호                  

                    is_vibrating = True
                    #회전을 하기 전까지 index는 바뀌지 않음. 따라서 중복신호 방지 가능
                    last_vibrated_index = current_index

            # 신호 종료
            # 현재 인덱스가 진동을 시작했던 인덱스보다 커지면 통과한 것으로 간주
            elif is_vibrating and current_index > last_vibrated_index:
                print(f"[EVENT] 안내 지점(Index {last_vibrated_index}) 통과 - 진동 종료")
                
                # 양쪽 장갑에 모두 정지 신호를 보냄
                await ble_service.stop_vibration("left")
                await ble_service.stop_vibration("right")
                # LED 소등 신호

                
                is_vibrating = False
            # 데이터 갱신 주기 (1초)
            await asyncio.sleep(1)

        except Exception as e:
            print(f"오류 발생: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())