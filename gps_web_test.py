"""
GPS 수신 테스트 전용 실행 파일
- main.py와 달리 TMAP / BLE / LED 없이, GPS 수신 + 웹서버만 실행한다.
- 야외에서 스마트폰으로 GPS 데이터가 잘 들어오는지 확인하는 용도.

실행 방법:
    1) (최초 1회) 라즈베리파이에 Flask 설치:  pip install flask
    2) python gps_web_test.py
    3) 라즈베리파이 IP 확인:  hostname -I
    4) 같은 핫스팟에 연결된 스마트폰 브라우저에서 접속:
       http://<라즈베리파이IP>:5000
"""

import asyncio
from services import gps_service, gps_web_service


async def main():
    print("=== GPS 수신 테스트 (웹 모드) ===")

    # 1. Flask 웹서버 시작 (별도 스레드 → GPS 루프를 막지 않음)
    gps_web_service.start_web_server(port=5000)
    print("[WEB] 웹서버 시작됨")
    print("[WEB] 스마트폰에서 접속:  http://<라즈베리파이IP>:5000")
    print("[WEB] (라즈베리파이 IP는 'hostname -I' 로 확인)")

    # 2. GPS 백그라운드 수신 루프 실행 (이 호출이 계속 돌아감)
    await gps_service.gps_loop()


if __name__ == "__main__":
    asyncio.run(main())