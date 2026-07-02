# Robot Kafa v12 Türkçe Kullanım Rehberi

## 1. Dosyaların yüklenmesi

RP2350'ye `microcontrollerside/` klasöründeki bütün dosyaları yükle. Yalnızca
`main.py` yüklemek yeterli değildir. Yeni hareketler için özellikle şu dosyalar
güncel olmalıdır:

```text
microcontrollerside/main.py
microcontrollerside/config.py
microcontrollerside/head_gesture_controller.py
microcontrollerside/arm_controller.py
microcontrollerside/serial_parser.py
```

Raspberry Pi tarafında `robot_head_project/` klasörünü kullan.

## 2. Programı çalıştırma

```bash
cd robot_head_project
python3 main.py
```

OpenCV kamera penceresi açıldığında pencerenin görüntü kısmına bir kez tıkla.
Tuşlar terminalden değil, bu pencereden okunur.

## 3. MANUAL moda geçme

```text
2 -> MANUAL
```

Sağdaki durum panelinde `CONTROL MODE: MANUAL` görünmelidir.

## 4. Yeni hareketler

```text
6 -> DANCE
7 -> GREET
8 -> DAISY_DANCE
0 -> hareketi iptal et
```

### DANCE

Güneş gözlüklü yüz gelir. Kafa sağa-sola dönerken tilt aynı anda yukarı-aşağı
hareket eder.

Bir tekrar:

```text
sağ + yukarı
merkez + aşağı
sol + yukarı
merkez + aşağı
```

### GREET

Güneş gözlüklü yüz gelir. Kafa önce sağa döner ve belirlenen sayıda nod yapar,
sonra sola döner ve aynı sayıda nod yapar.

### DAISY_DANCE

`DANCE` kafa hareketine ek olarak iki kol zıt yönlerde ritmik hareket eder.
Hareket bitince kafa başlangıç pozisyonuna, kollar nötr pozisyona döner.

## 5. Tekrar sayısı ve yüz kilidi

Raspberry Pi tarafında:

```text
robot_head_project/config.py
```

```python
MANUAL_GESTURE_COUNT = 3
MANUAL_FACE_HOLD_MS = 4000
```

`MANUAL_GESTURE_COUNT = 3` olduğunda:

- `DANCE`: üç tam dans döngüsü yapar.
- `GREET`: sağda üç ve solda üç nod yapar.
- `DAISY_DANCE`: üç kafa-kol dans döngüsü yapar.

`MANUAL_FACE_HOLD_MS`, yüzün IMU tarafından değiştirilmesini engelleyen süreyi
milisaniye olarak belirler. Aktif hareket devam ettiği sürece, bu süre bitmiş
olsa bile `RUNNING` ve `DIZZY` yüzleri hareket yüzünü ezemez.

## 6. Python fonksiyonları

```python
robot_head.dance(count=3, hold_ms=7000)
robot_head.greet(nod_count=3, hold_ms=7000)
robot_head.daisy_dance(count=3, hold_ms=8000)
robot_head.cancel_gesture()
```

Doğrudan Python çağrıları varsayılan olarak MANUAL kaynağıdır. Önce:

```python
mode_manager.set_mode(ControlMode.MANUAL)
```

ROS kaynağı için:

```python
robot_head.dance(
    count=3,
    hold_ms=7000,
    source=ControlMode.ROS,
)
```

## 7. Seri komutlar

```text
GESTURE:DANCE,3,7000
GESTURE:GREET,3,7000
GESTURE:DAISY_DANCE,3,8000
GESTURE:CANCEL
```

Format:

```text
GESTURE:HAREKET_ADI,TEKRAR_SAYISI,HOLD_MS
```


## 8. Smooth servo hareketi

Pan ve tilt artık sabit derece sıçramalarıyla değil, RP2350 üzerinde zamana bağlı
hızlanma ve yavaşlama profiliyle hareket eder. Ayarlar:

```python
HEAD_PAN_MAX_SPEED_DEG_S = 140.0
HEAD_PAN_ACCEL_DEG_S2 = 400.0
HEAD_PAN_MOTION_UPDATE_INTERVAL_MS = 20

HEAD_TILT_MAX_SPEED_DEG_S = 100.0
HEAD_TILT_ACCEL_DEG_S2 = 300.0
HEAD_TILT_MOTION_UPDATE_INTERVAL_MS = 20
```

Senin güncel tilt güvenli sınırların korunmuştur:

```python
HEAD_TILT_MIN_LIMIT_ANGLE = 75.0
HEAD_TILT_MAX_LIMIT_ANGLE = 120
```

`LOOK_AROUND`, aşağıdaki değer `True` iken dişli oranı ve servo limitlerinden
hesaplanan tam ulaşılabilir sağ-sol aralığı kullanır:

```python
GESTURE_LOOK_AROUND_USE_FULL_RANGE = True
```

## 9. Hareket ayarları

RP2350 tarafındaki hareket açıları:

```text
microcontrollerside/config.py
```

```python
GESTURE_DANCE_PAN_OFFSET_DEG = 30.0
GESTURE_DANCE_TILT_UP_OFFSET_DEG = 9.0
GESTURE_DANCE_TILT_DOWN_OFFSET_DEG = -9.0
GESTURE_DANCE_DWELL_MS = 150

GESTURE_GREET_PAN_OFFSET_DEG = 35.0
GESTURE_GREET_NOD_UP_OFFSET_DEG = 9.0
GESTURE_GREET_NOD_DOWN_OFFSET_DEG = -9.0
GESTURE_GREET_TURN_DWELL_MS = 260
GESTURE_GREET_NOD_DWELL_MS = 130

ARM_DANCE_AMPLITUDE_DEG = 35
ARM_DANCE_INTERVAL_MS = 160
ARM_DANCE_BEATS_PER_CYCLE = 4
```

İlk fiziksel testte bu değerleri artırma. Mekanik yönlerden biri tersse yalnızca
ilgili offset değerlerinin işaretlerini değiştir.

## 10. Diğer MANUAL tuşları

```text
1 AUTO             2 MANUAL           3 ROS
J/L pan             I/K tilt
C center            S stop
A kol sallama       F curious
4 sigma             5 sunglasses
N nod               O sunglasses nod
G sigma nod         X shake
B look around       M celebrate
Z sleep             W wake up
E acil durdurma     Q çıkış
```


## v13: Tilt titreşimi ve gesture merkezleme

Aşağı yöndeki tilt hareketi artık daha düşük hız ve ivmeyle yürütülür:

```python
HEAD_TILT_DOWN_MAX_SPEED_DEG_S = 38.0
HEAD_TILT_DOWN_ACCEL_DEG_S2 = 80.0
HEAD_TILT_TARGET_TOLERANCE_DEG = 0.60
HEAD_TILT_MIN_COMMAND_CHANGE_DEG = 0.25
```

`NOD`, `SHAKE`, `LOOK_AROUND`, `CELEBRATE`, `DANCE`, `GREET`, `DAISY_DANCE`, `SUNGLASSES_NOD` ve `SIGMA_NOD` önce pan=90 ve tilt=90 merkez pozisyonuna gelir. Merkezde 250 ms bekledikten sonra koreografi başlar.

```python
GESTURE_CENTER_BEFORE_START = True
GESTURE_CENTER_DWELL_MS = 250
```

Tilt hâlâ aşağı inerken mekanik olarak titriyorsa ilk ayarlanacak değerler `HEAD_TILT_DOWN_MAX_SPEED_DEG_S` ve `HEAD_TILT_DOWN_ACCEL_DEG_S2` değerleridir. Daha da yumuşak bir deneme için sırasıyla `30.0` ve `60.0` kullanılabilir.


---

## V14: LCD text and THINKING face

MANUAL modda OpenCV penceresine tıkladıktan sonra:

```text
9  -> THINKING yüzü
[  -> italik Oopsie Daisy yazısı
]  -> config.py içindeki genel metin
```

Python API:

```python
robot_head.show_oopsie_daisy(hold_ms=5000)
robot_head.show_text("Hello from Daisy", hold_ms=4000, italic=False)
robot_head.show_thinking(hold_ms=4000)
```

ROS2:

```bash
ros2 topic pub --once /robot_head/text   std_msgs/msg/String "{data: '5000|1|Oopsie Daisy'}"

ros2 service call /robot_head/oopsie_daisy_service   std_srvs/srv/Trigger "{}"
```

Ayrıntılar için `LCD_TEXT_THINKING_GUIDE.md` dosyasına bakın.

---

## ROS2 Docker modu (V15)

Tam kurulum ve uzak bilgisayar kullanımı için:

```text
ROS2_DOCKER_GUIDE_TR.md
ROS2_API.md
```

Pi OS ana programını çalıştır:

```bash
cd robot_head_project
python3 main.py
```

Ayrı terminalde container'ı başlat:

```bash
cd ..
cp .env.ros2.example .env
docker compose -f compose.ros2.yaml up -d --build
```

Container `network_mode: host` kullanır ve ana programa
`127.0.0.1:8765` üzerinden bağlanır.
