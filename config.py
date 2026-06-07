import os
from dotenv import load_dotenv

load_dotenv()

#수신기 주소
BLE_LEFT_MAC = os.getenv("BLE_LEFT_MAC")
BLE_RIGHT_MAC = os.getenv("BLE_RIGHT_MAC")

CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"