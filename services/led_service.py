import asyncio
from rpi_ws281x import PixelStrip, Color # type: ignore
# rpi_ws281x가 라즈베리파이 전용 라이브러리라 로컬에서 따로 설치는 안했습니다
# requirements에 추가는 해놨으니까 딱히 문제는 없습니다

# === LED 하드웨어 공통 설정 ===
LED_COUNT = 16        # LED Strip 1개당 16구의 LED가 있음
LED_FREQ_HZ = 800000  # LED 신호 주파수
LED_BRIGHTNESS = 100  # 전력때문에 밝기 40% 수준으로 제한(맥스값 255)
LED_INVERT = False    

# 왼쪽 장갑 스트립 설정
LEFT_PIN = 18 #GPIO 번호
LEFT_CHANNEL = 0
LEFT_DMA = 10
strip_left = PixelStrip(LED_COUNT, LEFT_PIN, LED_FREQ_HZ, LEFT_DMA, LED_INVERT, LED_BRIGHTNESS, LEFT_CHANNEL)
strip_left.begin()

# 오른쪽 장갑 스트립 설정
RIGHT_PIN = 13 #GPIO 번호
RIGHT_CHANNEL = 1
RIGHT_DMA = 11  # 하드웨어 충돌 방지를 위해 DMA 채널을 11번으로 다르게 배정
strip_right = PixelStrip(LED_COUNT, RIGHT_PIN, LED_FREQ_HZ, RIGHT_DMA, LED_INVERT, LED_BRIGHTNESS, RIGHT_CHANNEL)
strip_right.begin()

# 현재 점등 됐는지 여부를 확인하는 변수
_blink_task = None

async def _blink_loop(direction):
    """실제 LED를 0.6초 ON / 0.2초 OFF 깜빡이게 하는 비동기 루프"""
    
    # 필요 전력 감소를 위해 Blue 컬러 사용 X
    color = Color(255, 165, 0) # Red, Green, Blue
    
    active_strip = strip_left if direction == "left" else strip_right
    
    # 전력 절약을 위해 가운데 6개만 점등시킴
    led_range = range(5, 11)

    try:
        while True:
            # 1. 점등 (0.6초)
            for i in led_range:
                active_strip.setPixelColor(i, color)
            active_strip.show()
            await asyncio.sleep(0.6)
            
            # 2. 소등 (0.2초)
            for i in led_range:
                active_strip.setPixelColor(i, Color(0, 0, 0))
            active_strip.show()
            await asyncio.sleep(0.2)
            
    except asyncio.CancelledError:
        # 작업이 취소(stop)되면 현재 조작 중이던 스트립을 완전히 끔
        for i in range(LED_COUNT):
            active_strip.setPixelColor(i, Color(0, 0, 0))
        active_strip.show()

def start_led_blink(direction):
    """깜빡임 백그라운드 작업을 시작하는 함수"""
    global _blink_task
    stop_led() # 기존에 깜빡임이 있다면 중지, 어차피 미리 중지시킬거라 삭제해도 상관없는 코드
    
    # 비동기 루프를 백그라운드 Task로 실행 (메인 코드 멈춤 방지)
    _blink_task = asyncio.create_task(_blink_loop(direction))

def stop_led():
    """깜빡임 작업을 강제 종료하고 양쪽 불을 모두 끄는 함수"""
    global _blink_task
    if _blink_task and not _blink_task.done():
        _blink_task.cancel() #이걸로 작업 중단시킴
        _blink_task = None
        
    # 혹시를 대비한 강제 소등 코드. 이것도 지워도 상관없음
    for i in range(LED_COUNT):
        strip_left.setPixelColor(i, Color(0, 0, 0))
        strip_right.setPixelColor(i, Color(0, 0, 0))
    strip_left.show()
    strip_right.show()