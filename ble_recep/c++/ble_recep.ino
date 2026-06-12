#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

static const char* DEVICE_NAME = "SmartHelmet-Vibe";
static const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
static const char* COMMAND_CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8";

static const uint8_t VIBE_IN_PIN = 4;

static BLEAdvertising* bleWait = nullptr;
static bool connected = false;

// ==========================================
// ⏱️ 펄스 패턴 제어를 위한 상태 변수들
// ==========================================
bool isPatternActive = false;     // "1" 신호를 받아 현재 패턴이 실행 중인지 여부
bool currentMotorState = false;   // 현재 모터가 실제로 켜져 있는지 여부
unsigned long previousMillis = 0; // 스톱워치 기록용 변수

const unsigned long ON_TIME = 600;  // 진동 켜짐 시간 (0.6초)
const unsigned long OFF_TIME = 200; // 진동 꺼짐 시간 (0.2초)
// ==========================================

// 모터의 물리적 상태를 안전하게 제어하는 함수
static void setMotorPhysicalState(bool state) {
  if (state) {
    digitalWrite(VIBE_IN_PIN, HIGH);
    currentMotorState = true;
  } else {
    digitalWrite(VIBE_IN_PIN, LOW);
    currentMotorState = false;
  }
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
    isPatternActive = false; // 연결이 끊기면 즉시 패턴 정지
    setMotorPhysicalState(false);
    Serial.println("[BLE] 연결 끊김 (진동 정지)");

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
      // 규칙: 이미 켜져 있다면 추가로 들어오는 "1"은 무시합니다.
      if (!isPatternActive) {
        Serial.println("[진동] 패턴 시작! (0.6초 ON / 0.2초 OFF 반복)");
        isPatternActive = true;
        setMotorPhysicalState(true); // 즉시 1타 진동 시작
        previousMillis = millis();   // 스톱워치 초기화
      } else {
        Serial.println("[진동] 패턴 이미 실행 중 (중복 명령 무시)");
      }
    } 
    else if (command == "0" || command == "끄기" || command == "정지") {
      Serial.println("[진동] 명령 수신: 완전 정지");
      isPatternActive = false;      // 패턴 루프 종료
      setMotorPhysicalState(false); // 즉시 모터 끄기
    } 
    else {
      Serial.println("[BLE] 알 수 없는 명령");
    }
  }
};

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(VIBE_IN_PIN, OUTPUT);
  setMotorPhysicalState(false);

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

  Serial.println("=== 스마트 헬멧/장갑 ESP32-C3 진동 수신기 ===");
  Serial.print("[BLE] 장치 이름: ");
  Serial.println(DEVICE_NAME);
  Serial.println("[BLE] 연결 대기 중...");
}

void loop() {
  // isPatternActive가 true(1번 명령을 받은 상태)일 때만 스톱워치가 작동합니다.
  if (isPatternActive) {
    unsigned long currentMillis = millis(); // 현재 시간 확인

    if (currentMotorState) {
      // 모터가 켜져 있는 상태에서 ON_TIME(0.6초)이 경과했다면?
      if (currentMillis - previousMillis >= ON_TIME) {
        setMotorPhysicalState(false);   // 모터 끄기
        previousMillis = currentMillis; // 시간 리셋
      }
    } else {
      // 모터가 꺼져 있는 상태에서 OFF_TIME(0.2초)이 경과했다면?
      if (currentMillis - previousMillis >= OFF_TIME) {
        setMotorPhysicalState(true);    // 모터 켜기
        previousMillis = currentMillis; // 시간 리셋
      }
    }
  }

  // CPU 과부하 방지용 미세 휴식 (BLE 통신을 방해하지 않는 0.01초)
  delay(10); 
}