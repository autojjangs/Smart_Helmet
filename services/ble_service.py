
from bleak import BleakClient
import config



#신호 시작
async def start_vibration(direction):
    target_mac = config.BLE_LEFT_MAC if direction == "left" else config.BLE_RIGHT_MAC
    await send_vibration(target_mac, "1")

#신호 종료
async def stop_vibration(direction):
    target_mac = config.BLE_LEFT_MAC if direction == "left" else config.BLE_RIGHT_MAC
    await send_vibration(target_mac, "0")

async def send_vibration(mac_address, action):
    # 특성(Characteristic)에 '1' 또는 '0' 전송
    try:
        async with BleakClient(mac_address, timeout=3.0) as client:
            #3초간 연결시도
            if client.is_connected:
                await client.write_gatt_char(config.CHARACTERISTIC_UUID, bytearray(action, 'utf-8'))
    except Exception as e:
        print(f"[BLE Error] {mac_address} 통신 실패: {e}")