#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// 라즈베리파이의 ble_service.py에서도 같은 UUID를 사용해야 합니다.
static const char* DEVICE_NAME = "SmartHelmet-Vibe";
static const char* SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
static const char* COMMAND_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";

// EM-MA-126 진동모듈의 IN 핀에 연결된 ESP32-C3 GPIO 번호입니다.
// 현재 배선: GPIO n -> IN, 5V/VBUS -> VCC, GND -> GND
static const uint8_t VIBE_IN_PIN = n;

static BLEAdvertising* bleWait = nullptr;
static bool connected = false;

static void startVibration() {
  digitalWrite(VIBE_IN_PIN, HIGH);
  Serial.println("[진동] 켜짐");
}

static void stopVibration() {
  digitalWrite(VIBE_IN_PIN, LOW);
  Serial.println("[진동] 꺼짐");
}

static String normalizeCommand(String command) {
  command.trim();
  command.toLowerCase();
  command.replace(" ", "");
  command.replace("_", ":");
  return command;
}

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* server) override {
    connected = true;
    Serial.println("[BLE] 연결됨");
  }

  void onDisconnect(BLEServer* server) override {
    connected = false;
    stopVibration();
    Serial.println("[BLE] 연결 끊김");

    // BLE 스택이 정리될 시간을 잠시 준 뒤 다시 연결 대기 상태로 전환합니다.
    delay(100);
    if (bleWait != nullptr) {
      bleWait->start();
      Serial.println("[BLE] 연결 대기 재시작");
    }
  }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* characteristic) override {
    String command = normalizeCommand(characteristic->getValue().c_str());

    Serial.print("[BLE] 수신 명령: ");
    Serial.println(command);

    if (command == "1" || command == "켜기" || command == "시작") {
      startVibration();
    } else if (command == "0" || command == "끄기" || command == "정지") {
      stopVibration();
    } else {
      Serial.println("[BLE] 알 수 없는 명령");
    }
  }
};

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(VIBE_IN_PIN, OUTPUT);
  stopVibration();

  BLEDevice::init(DEVICE_NAME);
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

  BLEService* service = server->createService(SERVICE_UUID);
  BLECharacteristic* commandCharacteristic = service->createCharacteristic(
      COMMAND_CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  commandCharacteristic->setCallbacks(new CommandCallbacks());
  commandCharacteristic->addDescriptor(new BLE2902());

  service->start();

  bleWait = BLEDevice::getAdvertising();
  bleWait->addServiceUUID(SERVICE_UUID);
  bleWait->setScanResponse(true);
  bleWait->setMinPreferred(0x06);
  bleWait->setMinPreferred(0x12);
  bleWait->start();

  Serial.println("=== 스마트 헬멧 ESP32-C3 진동 수신기 ===");
  Serial.print("[BLE] 장치 이름: ");
  Serial.println(DEVICE_NAME);
  Serial.println("[BLE] 연결 대기 중...");
}

void loop() {
  delay(1000);
}
