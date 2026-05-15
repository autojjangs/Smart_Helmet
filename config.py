import os
from dotenv import load_dotenv

load_dotenv()

#수신기 주소
BLE_LEFT_MAC = os.getenv("BLE_LEFT_MAC")
BLE_RIGHT_MAC = os.getenv("BLE_RIGHT_MAC")

CHARACTERISTIC_UUID="추후 수신기파트랑 통일해서 작성"