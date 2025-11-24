# MQTT 코드 예제

**언어**: Python, C#
**최종 업데이트**: 2025-11-24

---

## Python 예제

### 기본 연결

```python
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print(f"MQTT 브로커 연결됨: {rc}")
    if rc == 0:
        print("✓ 연결 성공")
    else:
        print(f"✗ 연결 실패: {rc}")

def on_disconnect(client, userdata, rc):
    print(f"MQTT 브로커 연결 끊김: {rc}")

# 클라이언트 생성
client = mqtt.Client(client_id="robot_pc")
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# 브로커 연결
client.connect("192.168.0.14", 1883, 60)

# 이벤트 루프 시작
client.loop_forever()
```

---

### 메시지 발행 (로봇 PC)

#### 젯슨1: 볶음 제어

```python
import paho.mqtt.client as mqtt
import time

# 클라이언트 생성 및 연결
client = mqtt.Client(client_id="robot_pc")
client.connect("localhost", 1883, 60)
client.loop_start()

# POT1: 김치볶음 시작
client.publish("stirfry/pot1/food_type", "김치볶음", qos=1)
print("[발행] POT1 김치볶음 시작")

# 5분간 조리
time.sleep(300)

# POT1: 중지
client.publish("stirfry/pot1/control", "stop", qos=1)
print("[발행] POT1 중지")

# 정리
client.loop_stop()
client.disconnect()
```

---

#### 젯슨2: 튀김 제어 + 온도 전송

```python
import paho.mqtt.client as mqtt
import time
import random

# 클라이언트 생성 및 연결
client = mqtt.Client(client_id="robot_pc")
client.connect("localhost", 1883, 60)
client.loop_start()

# POT1: 치킨 튀김 시작
client.publish("frying/pot1/food_type", "치킨", qos=1)
print("[발행] POT1 치킨 시작")

# 온도 데이터 전송 (1초마다, 5분간)
start_time = time.time()
oil_temp = 165.0
probe_temp = 40.0

while time.time() - start_time < 300:  # 5분
    # 온도 상승 시뮬레이션
    oil_temp += random.uniform(0.1, 0.5)
    probe_temp += random.uniform(0.3, 0.7)

    # 기름 온도 전송
    client.publish("frying/pot1/oil_temp", f"{oil_temp:.1f}", qos=1)

    # 탐침 온도 전송
    client.publish("frying/pot1/probe_temp", f"{probe_temp:.1f}", qos=1)

    print(f"[발행] 기름: {oil_temp:.1f}°C, 탐침: {probe_temp:.1f}°C")

    # 75°C 도달 확인
    if probe_temp >= 75.0:
        print("[완료] 탐침 온도 75°C 도달! 자동 완료 마킹")

    time.sleep(1)

# POT1: 중지
client.publish("frying/pot1/control", "stop", qos=1)
print("[발행] POT1 중지")

# 정리
client.loop_stop()
client.disconnect()
```

---

### 메시지 구독 (로봇 PC)

#### 젯슨 상태 모니터링

```python
import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc):
    print(f"MQTT 브로커 연결됨: {rc}")

    # 젯슨1 사람 감지 구독
    client.subscribe("frying_ai/jetson1/robot/control")
    print("[구독] 젯슨1 사람 감지")

    # 젯슨2 바구니 상태 구독
    client.subscribe("jetson2/observe/status")
    print("[구독] 젯슨2 바구니 상태")

    # 모든 젯슨 AI 모드 구독 (wildcard)
    client.subscribe("+/system/ai_mode")
    print("[구독] 모든 젯슨 AI 모드")

    # 젯슨1 릴레이 상태 구독
    client.subscribe("jetson1/relay/status")
    print("[구독] 젯슨1 릴레이 상태")

def on_message(client, userdata, msg):
    print(f"\n[수신] 토픽: {msg.topic}")

    try:
        # JSON 메시지 파싱
        data = json.loads(msg.payload.decode())
        print(f"      메시지: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # 토픽별 처리
        if msg.topic == "frying_ai/jetson1/robot/control":
            handle_person_detection(data)
        elif msg.topic == "jetson2/observe/status":
            handle_basket_status(data)
        elif "/system/ai_mode" in msg.topic:
            handle_ai_mode(data)
        elif msg.topic == "jetson1/relay/status":
            handle_relay_status(data)

    except json.JSONDecodeError:
        # JSON이 아닌 단순 문자열
        print(f"      메시지: {msg.payload.decode()}")

def handle_person_detection(data):
    """사람 감지 처리"""
    command = data.get("command", "")
    person_detected = data.get("person_detected", False)

    if command == "ON" and person_detected:
        print("      [처리] ✓ 사람 감지됨 - 로봇 시작 준비")
    elif command == "OFF" and not person_detected:
        print("      [처리] ⏸ 사람 사라짐 - 로봇 대기 모드")

def handle_basket_status(data):
    """바구니 상태 처리"""
    message = data.get("message", "")

    if "BASKET_IN" in message:
        print("      [처리] 🥘 바구니에 음식 들어옴")
    elif "BASKET_OUT" in message:
        print("      [처리] ✓ 바구니에서 음식 나감")
    elif "NO_BASKET" in message:
        print("      [처리] ⚠ 바구니 없음")

def handle_ai_mode(data):
    """AI 모드 확인"""
    device_id = data.get("device_id", "")
    status = data.get("message", "")
    print(f"      [처리] 🤖 {device_id} AI 상태: {status}")

def handle_relay_status(data):
    """릴레이 상태 처리"""
    relay_status = data.get("relay_status", "")
    print(f"      [처리] 🔌 릴레이 상태: {relay_status}")

# 클라이언트 생성
client = mqtt.Client(client_id="robot_pc_monitor")
client.on_connect = on_connect
client.on_message = on_message

# 브로커 연결
client.connect("192.168.0.14", 1883, 60)

# 이벤트 루프 시작
print("[시작] MQTT 모니터링 시작...")
client.loop_forever()
```

---

### 진동 센서 제어

```python
import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time

# 클라이언트 생성 및 연결
client = mqtt.Client(client_id="robot_pc")
client.connect("localhost", 1883, 60)
client.loop_start()

# JSON 형태로 시작 명령
start_msg = {
    "command": "START",
    "source": "robot_pc",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

client.publish("calibration/vibration/control",
               json.dumps(start_msg, ensure_ascii=False),
               qos=1)
print(f"[발행] 진동 센서 시작: {start_msg}")

# 10분간 캘리브레이션
print("[대기] 10분간 진동 데이터 수집 중...")
time.sleep(600)

# JSON 형태로 종료 명령
stop_msg = {
    "command": "STOP",
    "source": "robot_pc",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

client.publish("calibration/vibration/control",
               json.dumps(stop_msg, ensure_ascii=False),
               qos=1)
print(f"[발행] 진동 센서 종료: {stop_msg}")

# 정리
client.loop_stop()
client.disconnect()
```

---

## C# 예제

### 기본 연결 (MQTTnet 사용)

```csharp
using MQTTnet;
using MQTTnet.Client;
using System;
using System.Text;
using System.Threading.Tasks;

class MQTTExample
{
    private static IMqttClient mqttClient;

    static async Task Main(string[] args)
    {
        // MQTT 클라이언트 생성
        var factory = new MqttFactory();
        mqttClient = factory.CreateMqttClient();

        // 연결 옵션 설정
        var options = new MqttClientOptionsBuilder()
            .WithTcpServer("192.168.0.14", 1883)
            .WithClientId("robot_pc_csharp")
            .WithCleanSession()
            .Build();

        // 연결 이벤트 핸들러
        mqttClient.ConnectedAsync += async e =>
        {
            Console.WriteLine("✓ MQTT 브로커 연결됨");

            // 구독 설정
            await SubscribeToTopics();
        };

        // 연결 끊김 이벤트 핸들러
        mqttClient.DisconnectedAsync += async e =>
        {
            Console.WriteLine("✗ MQTT 브로커 연결 끊김");
            await Task.Delay(TimeSpan.FromSeconds(5));

            try
            {
                await mqttClient.ConnectAsync(options);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"재연결 실패: {ex.Message}");
            }
        };

        // 메시지 수신 핸들러
        mqttClient.ApplicationMessageReceivedAsync += OnMessageReceived;

        // 브로커 연결
        await mqttClient.ConnectAsync(options);

        Console.WriteLine("Press Enter to exit...");
        Console.ReadLine();

        await mqttClient.DisconnectAsync();
    }

    static async Task SubscribeToTopics()
    {
        // 젯슨1 사람 감지 구독
        await mqttClient.SubscribeAsync("frying_ai/jetson1/robot/control");
        Console.WriteLine("[구독] 젯슨1 사람 감지");

        // 젯슨2 바구니 상태 구독
        await mqttClient.SubscribeAsync("jetson2/observe/status");
        Console.WriteLine("[구독] 젯슨2 바구니 상태");

        // AI 모드 구독
        await mqttClient.SubscribeAsync("+/system/ai_mode");
        Console.WriteLine("[구독] 모든 젯슨 AI 모드");
    }

    static Task OnMessageReceived(MqttApplicationMessageReceivedEventArgs e)
    {
        var topic = e.ApplicationMessage.Topic;
        var payload = Encoding.UTF8.GetString(e.ApplicationMessage.Payload);

        Console.WriteLine($"\n[수신] 토픽: {topic}");
        Console.WriteLine($"      메시지: {payload}");

        // 토픽별 처리
        if (topic == "frying_ai/jetson1/robot/control")
        {
            HandlePersonDetection(payload);
        }
        else if (topic == "jetson2/observe/status")
        {
            HandleBasketStatus(payload);
        }

        return Task.CompletedTask;
    }

    static void HandlePersonDetection(string payload)
    {
        // JSON 파싱 및 처리
        Console.WriteLine("      [처리] 사람 감지 이벤트 처리");
    }

    static void HandleBasketStatus(string payload)
    {
        // JSON 파싱 및 처리
        Console.WriteLine("      [처리] 바구니 상태 이벤트 처리");
    }
}
```

---

### 메시지 발행 (C#)

```csharp
using MQTTnet;
using MQTTnet.Client;
using System;
using System.Text;
using System.Threading.Tasks;

class MQTTPublisher
{
    static async Task Main(string[] args)
    {
        // MQTT 클라이언트 생성
        var factory = new MqttFactory();
        var mqttClient = factory.CreateMqttClient();

        // 연결
        var options = new MqttClientOptionsBuilder()
            .WithTcpServer("localhost", 1883)
            .WithClientId("robot_pc_publisher")
            .Build();

        await mqttClient.ConnectAsync(options);
        Console.WriteLine("✓ MQTT 브로커 연결됨");

        // POT1 김치볶음 시작
        await PublishMessage(mqttClient, "stirfry/pot1/food_type", "김치볶음");
        Console.WriteLine("[발행] POT1 김치볶음 시작");

        // 5분 대기
        await Task.Delay(TimeSpan.FromMinutes(5));

        // POT1 중지
        await PublishMessage(mqttClient, "stirfry/pot1/control", "stop");
        Console.WriteLine("[발행] POT1 중지");

        // 연결 종료
        await mqttClient.DisconnectAsync();
    }

    static async Task PublishMessage(IMqttClient client, string topic, string payload)
    {
        var message = new MqttApplicationMessageBuilder()
            .WithTopic(topic)
            .WithPayload(payload)
            .WithQualityOfServiceLevel(MQTTnet.Protocol.MqttQualityOfServiceLevel.AtLeastOnce)
            .WithRetainFlag(false)
            .Build();

        await client.PublishAsync(message);
    }
}
```

---

## 유용한 스니펫

### 멀티 POT 동시 제어

```python
import paho.mqtt.client as mqtt
import time

client = mqtt.Client(client_id="robot_pc")
client.connect("localhost", 1883, 60)
client.loop_start()

# POT1, POT2 동시 시작
client.publish("stirfry/pot1/food_type", "김치볶음", qos=1)
client.publish("stirfry/pot2/food_type", "야채볶음", qos=1)
print("[발행] POT1 김치볶음, POT2 야채볶음 동시 시작")

# 5분 후 POT1만 중지
time.sleep(300)
client.publish("stirfry/pot1/control", "stop", qos=1)
print("[발행] POT1 중지")

# 5분 더 조리 후 POT2 중지
time.sleep(300)
client.publish("stirfry/pot2/control", "stop", qos=1)
print("[발행] POT2 중지")

client.loop_stop()
client.disconnect()
```

---

### 에러 처리

```python
import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ 연결 성공")
    else:
        print(f"✗ 연결 실패: {rc}")
        print("  0: 연결 성공")
        print("  1: 잘못된 프로토콜 버전")
        print("  2: 잘못된 클라이언트 ID")
        print("  3: 서버 사용 불가")
        print("  4: 잘못된 사용자명/비밀번호")
        print("  5: 권한 없음")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠ 예상치 못한 연결 끊김: {rc}")
        print("  5초 후 재연결 시도...")
        time.sleep(5)
        try:
            client.reconnect()
        except Exception as e:
            print(f"✗ 재연결 실패: {e}")

def on_publish(client, userdata, mid):
    print(f"✓ 메시지 발행 완료 (ID: {mid})")

client = mqtt.Client(client_id="robot_pc")
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish

try:
    client.connect("192.168.0.14", 1883, 60)
    client.loop_start()

    # 메시지 발행
    result = client.publish("stirfry/pot1/food_type", "김치볶음", qos=1)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"✗ 발행 실패: {result.rc}")

    time.sleep(2)

except Exception as e:
    print(f"✗ 에러 발생: {e}")
finally:
    client.loop_stop()
    client.disconnect()
```

---

## 테스트 도구

### MQTT 메시지 발행 도구

프로젝트에 포함된 `test_mqtt_publish.py` 사용:

```bash
cd ~/jetson-food-ai
python3 test_mqtt_publish.py
```

대화형 메뉴에서 메시지 타입 선택 가능.

---

## 패키지 설치

### Python

```bash
pip3 install paho-mqtt
```

### C#

```bash
dotnet add package MQTTnet
```

---

**버전**: 1.0
**최종 업데이트**: 2025-11-24
