"""
BLE 진동 장갑 서비스 (ble_service.py)  -- 라이브러리: bleak

[변경점: 연결 1회 유지(persistent connection)]
  - 기존에는 start/stop_vibration 호출마다 'async with BleakClient(...)'로
    매번 새로 연결→쓰기→해제했다. 2초 주기 루프에서 연결 지연(최대 timeout)이 반복되어
    루프가 밀릴 수 있었다.
  - 이제 connect_all()로 좌/우 장갑에 한 번 연결해 두고, 그 BleakClient를 재사용해
    write_gatt_char만 보낸다. 연결이 끊겼으면 1회 자동 재연결한다.
  - 종료 시 disconnect_all()로 정리한다.
  - set_simulation(True)이면 실제 연결 없이 로그만 남긴다(테스트용).

[주의] bleak은 asyncio 기반이라 connect/write/disconnect는 모두
       내비게이션이 도는 동일 이벤트 루프 안에서 호출되어야 한다(현재 구조가 그러함).
"""

import config

# === 내부 상태 ===
_sim = False
_clients = {}          # {"left": BleakClient|None, "right": BleakClient|None}
_BleakClient = None    # bleak.BleakClient (실제 모드에서만 lazy import)


def set_simulation(flag):
    """시뮬레이션 모드 on/off. 내비 시작 전에 호출."""
    global _sim
    _sim = flag


def _mac(direction):
    return config.BLE_LEFT_MAC if direction == "left" else config.BLE_RIGHT_MAC


async def connect_all():
    """좌/우 장갑에 미리 연결을 수립한다(내비 시작 시 1회)."""
    if _sim:
        print("[BLE] 시뮬레이션 모드 — 실제 연결을 수행하지 않습니다.")
        return
    for d in ("left", "right"):
        await _ensure_connected(d)


async def _ensure_connected(direction):
    """해당 방향 장갑이 연결돼 있으면 그 클라이언트를, 아니면 새로 연결해서 반환."""
    global _BleakClient

    if _sim:
        return None

    if _BleakClient is None:
        # 실제 모드에서만 bleak import (테스트/PC 환경 보호)
        from bleak import BleakClient
        _BleakClient = BleakClient

    client = _clients.get(direction)
    if client is not None and client.is_connected:
        return client

    mac = _mac(direction)
    if not mac:
        print(f"[BLE] {direction} MAC 주소가 설정되어 있지 않습니다(.env 확인).")
        return None

    client = _BleakClient(mac, timeout=5.0)
    try:
        await client.connect()
        _clients[direction] = client
        print(f"[BLE] {direction} 연결 성공 ({mac})")
        return client
    except Exception as e:
        print(f"[BLE Error] {direction} 연결 실패: {e}")
        _clients[direction] = None
        return None


async def _write(direction, action):
    """연결을 재사용해 '1'/'0'을 전송. 끊겼으면 1회 재연결 후 재시도."""
    if _sim:
        print(f"[BLE-SIM] {direction} ← '{action}'")
        return

    client = await _ensure_connected(direction)
    if client is None:
        return

    try:
        await client.write_gatt_char(config.CHARACTERISTIC_UUID, bytearray(action, "utf-8"))
    except Exception as e:
        print(f"[BLE Error] {direction} 쓰기 실패 — 재연결 후 재시도: {e}")
        _clients[direction] = None
        client = await _ensure_connected(direction)
        if client is not None:
            try:
                await client.write_gatt_char(config.CHARACTERISTIC_UUID, bytearray(action, "utf-8"))
            except Exception as e2:
                print(f"[BLE Error] {direction} 재시도 실패: {e2}")


# 신호 시작
async def start_vibration(direction):
    await _write(direction, "1")


# 신호 종료
async def stop_vibration(direction):
    await _write(direction, "0")


async def disconnect_all():
    """모든 BLE 연결 해제(내비 종료 시)."""
    if _sim:
        return
    for d, client in list(_clients.items()):
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
                print(f"[BLE] {d} 연결 해제")
            except Exception:
                pass
    _clients.clear()