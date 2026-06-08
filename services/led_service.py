"""
LED 서비스 (led_service.py) - 단일 체인(32구) 버전

[배경] PWM 스트립 2개를 각각 독립 PixelStrip으로 만들어 PWM0+PWM1 / DMA 10+11을
       동시에 쓰면 라즈베리파이 4에서 'ws2811_render failed code -10 (DMA error)'가 난다.
       rpi_ws281x는 '디바이스 1개 + DMA 1개'가 정상 사용법이므로,
       좌/우 16구 스트립을 물리적으로 이어 32구 한 줄로 만들고
       데이터 핀 하나(GPIO18/PWM0) + DMA 하나(10) + PixelStrip 하나로 제어한다.

[배선] Pi GPIO18 -> (왼쪽 16구) DIN, 왼쪽 DOUT -> (오른쪽 16구) DIN.
       전원 5V/GND는 양쪽 모두에, Pi와 GND 공통. (긴 데이터선엔 직렬저항/레벨시프터 권장)

[필수] 단일 스트립이라도 GPIO18은 내장 오디오(PWM0)와 충돌하므로
       /boot(/firmware)/config.txt 에서 dtparam=audio=off + 재부팅이 여전히 필요하다.

[좌/우 구분] 별도 객체 대신 '인덱스 구간'으로 구분한다.
       왼쪽 = 인덱스 0..15, 오른쪽 = 인덱스 16..31 (배선 순서가 반대면 OFFSET만 바꾸면 됨)

[지연 초기화] 실제 하드웨어 import/생성/begin()은 init(simulation=False)에서만 수행.
       init(simulation=True)이면 하드웨어를 건드리지 않고 로그만 남긴다(테스트).
"""

import asyncio

# === LED 하드웨어 공통 설정 ===
LEFT_COUNT = 10
RIGHT_COUNT = 10
LED_COUNT = LEFT_COUNT + RIGHT_COUNT   # 32 (한 줄로 합친 전체 개수)

LED_PIN = 18          # GPIO 18 = PWM0 (단일 데이터 핀)
LED_CHANNEL = 0       # PWM0 -> 채널 0
LED_DMA = 10          # DMA 채널 (단일)
LED_FREQ_HZ = 800000
LED_BRIGHTNESS = 50
LED_INVERT = False

# 좌/우 구간 매핑 (배선 순서가 반대라면 두 OFFSET 값을 서로 바꾸면 된다)
RIGHT_OFFSET = 0            # 왼쪽 장갑 = 0..9
LEFT_OFFSET = RIGHT_COUNT  # 오른쪽 장갑 = 10..19

# 각 장갑 16구 중 가운데 6구만 점등(전력 절약)
BLINK_SPAN = range(3, 7)

# === 내부 상태 (lazy init) ===
_sim = False
_initialized = False
strip = None          # 단일 PixelStrip(32구)
_Color = None
_blink_task = None


def init(simulation=False):
    """LED 사용 전 1회 호출. 실제 모드(simulation=False)는 root 권한 필요."""
    global _sim, _initialized, strip, _Color

    if _initialized:
        return

    _sim = simulation

    if _sim:
        _initialized = True
        print("[LED] 시뮬레이션 모드로 초기화 (실제 하드웨어 미사용)")
        return

    # ---- 실제 하드웨어 초기화 (여기서만 rpi_ws281x import) ----
    from rpi_ws281x import PixelStrip, Color  # type: ignore
    _Color = Color

    # 단일 디바이스 / 단일 DMA / 단일 채널
    strip = PixelStrip(
        LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL
    )
    strip.begin()

    _initialized = True
    print(f"[LED] 하드웨어 초기화 완료 (단일 체인 {LED_COUNT}구, GPIO{LED_PIN}/DMA{LED_DMA})")


def _ensure_initialized():
    if not _initialized:
        init(simulation=False)


def _blink_indices(direction):
    """방향에 해당하는 점등 인덱스 목록(전체 32구 기준)."""
    base = LEFT_OFFSET if direction == "left" else RIGHT_OFFSET
    return [base + i for i in BLINK_SPAN]


def _safe_show():
    """render(show) 예외가 내비 루프를 멈추지 않도록 보호."""
    try:
        strip.show()
    except Exception as e:
        # 일시적 렌더 오류는 로그만 남기고 다음 주기에 재시도
        print(f"[LED] show() 실패(무시하고 계속): {e}")


async def _blink_loop(direction):
    """단일 스트립에서 해당 방향 구간만 0.6초 ON / 0.2초 OFF."""
    _ensure_initialized()

    if _sim:
        idx = _blink_indices(direction)
        print(f"[LED-SIM] {direction} 깜빡임 시작 (인덱스 {idx[0]}~{idx[-1]})")
        try:
            while True:
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            print(f"[LED-SIM] {direction} 깜빡임 정지")
        return

    # 실제 하드웨어
    on_color = _Color(255, 130, 0)   # 주황
    off_color = _Color(0, 0, 0)
    indices = _blink_indices(direction)
    
    try:
        while True:
            # ON: 전체 끈 뒤 해당 방향 구간만 점등(반대쪽이 켜져 있지 않도록 보장)
            for i in range(LED_COUNT):
                strip.setPixelColor(i, off_color)
            for i in indices:
                strip.setPixelColor(i, on_color)
            _safe_show()
            await asyncio.sleep(0.6)

            # OFF: 전체 소등
            for i in range(LED_COUNT):
                strip.setPixelColor(i, off_color)
            _safe_show()
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        for i in range(LED_COUNT):
            strip.setPixelColor(i, off_color)
        _safe_show()


def start_led_blink(direction):
    """깜빡임 시작. (실행 중인 asyncio 이벤트 루프 안에서 호출)"""
    global _blink_task
    stop_led()  # 기존 깜빡임 정지
    _blink_task = asyncio.create_task(_blink_loop(direction))


def stop_led():
    """깜빡임 정지 + 전체 소등."""
    global _blink_task
    if _blink_task and not _blink_task.done():
        _blink_task.cancel()
    _blink_task = None

    if _initialized and not _sim:
        for i in range(LED_COUNT):
            strip.setPixelColor(i, _Color(0, 0, 0))
        _safe_show()
