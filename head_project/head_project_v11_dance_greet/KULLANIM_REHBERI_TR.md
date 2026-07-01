# Robot Kafa v11 Türkçe Kullanım Rehberi

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
MANUAL_GESTURE_COUNT = 2
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
robot_head.greet(nod_count=2, hold_ms=7000)
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
GESTURE:GREET,2,7000
GESTURE:DAISY_DANCE,3,8000
GESTURE:CANCEL
```

Format:

```text
GESTURE:HAREKET_ADI,TEKRAR_SAYISI,HOLD_MS
```

## 8. Hareket ayarları

RP2350 tarafındaki hareket açıları:

```text
microcontrollerside/config.py
```

```python
GESTURE_DANCE_PAN_OFFSET_DEG = 14.0
GESTURE_DANCE_TILT_UP_OFFSET_DEG = 5.0
GESTURE_DANCE_TILT_DOWN_OFFSET_DEG = -5.0
GESTURE_DANCE_DWELL_MS = 150

GESTURE_GREET_PAN_OFFSET_DEG = 20.0
GESTURE_GREET_NOD_UP_OFFSET_DEG = 5.0
GESTURE_GREET_NOD_DOWN_OFFSET_DEG = -5.0
GESTURE_GREET_TURN_DWELL_MS = 260
GESTURE_GREET_NOD_DWELL_MS = 130

ARM_DANCE_AMPLITUDE_DEG = 25
ARM_DANCE_INTERVAL_MS = 160
ARM_DANCE_BEATS_PER_CYCLE = 4
```

İlk fiziksel testte bu değerleri artırma. Mekanik yönlerden biri tersse yalnızca
ilgili offset değerlerinin işaretlerini değiştir.

## 9. Diğer MANUAL tuşları

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
