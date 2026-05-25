import asyncio
from rpi_ws281x import PixelStrip, Color #type: ignore
#rpi_ws281x가 라즈베리파이 전용 라이브러리라 로컬에서 따로 설치는 안했습니다
#requirments에 추가는 해놨으니까 딱히 문제는 없습니다

# === LED 하드웨어 설정 ===
LED_COUNT = 32        # 전체 LED 개수 (16구 * 2개 직렬 연결), 라즈베리파이와 먼저 연결된 애가 0~15번을 가짐
LED_PIN = 18          # GPIO 18번 (라즈베리파이에서 PWM을 지원하는 18번 핀 필수)
LED_FREQ_HZ = 800000  # LED 신호 주파수
LED_DMA = 10          # DMA 채널
LED_BRIGHTNESS = 100  # 전력때문에 밝기 40% 수준으로 제한
LED_INVERT = False    
LED_CHANNEL = 0       

# 스트립 초기화
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# 현재 실행 중인 깜빡임 작업을 저장할 변수
_blink_task = None

async def _blink_loop(direction):
    """실제 LED를 0.6초 ON / 0.2초 OFF 깜빡이게 하는 비동기 루프"""
    
    # 주황색 사용, 딱히 이유는 크게 없고 파란색 사용을 제한해서 전력 소모를 줄이기 위함
    color = Color(255, 165, 0) # Red, Green, Blue
    
    # 16개 중 가운데 6개만 켬
    if direction == "left":
        led_range = range(5, 11)   # 0~15번 중 5~10번 점등
    else: # right일떄
        led_range = range(21, 27)  # 16~31번 중 21~26번 점등

    try:
        while True:
            # 1. 점등 (0.6초)
            for i in led_range:
                strip.setPixelColor(i, color)
            strip.show()
            await asyncio.sleep(0.6)
            
            # 2. 소등 (0.2초)
            for i in led_range:
                strip.setPixelColor(i, Color(0, 0, 0))
            strip.show()
            await asyncio.sleep(0.2)
            
    except asyncio.CancelledError:
        # 작업이 취소(stop)되면 LED를 완전히 끔
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

def start_led_blink(direction):
    """깜빡임 백그라운드 작업을 시작하는 함수"""
    global _blink_task
    stop_led() # 기존에 돌고 있던 깜빡임이 있다면 중지
    
    # 비동기 루프를 백그라운드 Task로 실행 (메인 코드 멈춤 방지)
    _blink_task = asyncio.create_task(_blink_loop(direction))

def stop_led():
    """깜빡임 작업을 강제 종료하고 불을 끄는 함수"""
    global _blink_task
    if _blink_task and not _blink_task.done():
        _blink_task.cancel()
        _blink_task = None
        #작업 초기화 완료