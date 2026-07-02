# Little Daisy ROS2 + Docker Kullanım Rehberi

Bu sürümde Raspberry Pi OS üzerindeki ana uygulama kamera, görüntü işleme ve
RP2350 seri portunun sahibi olarak kalır. Docker container yalnızca ROS2 node'u
çalıştırır. İki süreç aynı seri portu açmaz.

## Mimari

```text
Uzak ROS2 bilgisayarı
        |
        | DDS / ROS2 ağı
        v
Pi 5 Docker container -- network_mode: host
        |
        | 127.0.0.1:8765 JSON bridge
        v
Pi OS robot_head_project/main.py
        |
        | /dev/ttyACM* 115200 baud
        v
RP2350
```

## 1. Raspberry Pi OS ana uygulamasını çalıştır

Önce kullandığın Python environment'ı etkinleştir, ardından:

```bash
cd ~/head_project_v15_ros2_docker_ready/robot_head_project
python3 main.py
```

Başlangıçta şunu görmelisin:

```text
ROS Docker command server listening on 127.0.0.1:8765
```

Ana uygulama AUTO modda başlayabilir. Docker node bağlandığında varsayılan
olarak modu ROS'a geçirir. Klavyeden de OpenCV penceresinde `3` tuşuyla ROS
moduna geçebilirsin.

İstersen ana uygulamayı doğrudan ROS modunda başlat:

```bash
ROBOT_HEAD_STARTUP_MODE=ROS python3 main.py
```

Yerel bridge ayarları:

```bash
ROBOT_HEAD_ENABLE_ROS_COMMAND_SERVER=true
ROBOT_HEAD_ROS_COMMAND_HOST=127.0.0.1
ROBOT_HEAD_ROS_COMMAND_PORT=8765
```

`127.0.0.1` güvenli varsayılandır. Bu TCP portunu internet veya LAN'a açman
gerekmez; host-network container aynı localhost ağına erişebilir.

## 2. ROS2 Docker image'ını oluştur

Proje kökünde:

```bash
cd ~/head_project_v15_ros2_docker_ready
cp .env.ros2.example .env

docker compose -f compose.ros2.yaml build
```

Varsayılan image:

```text
ros:jazzy-ros-base
```

Hem Raspberry Pi hem uzak bilgisayarda aynı ROS2 dağıtımını kullanmak en kolay
ve güvenilir seçenektir.

## 3. Container'ı başlat

```bash
docker compose -f compose.ros2.yaml up -d
```

Durum:

```bash
docker compose -f compose.ros2.yaml ps
docker compose -f compose.ros2.yaml logs -f
```

Beklenen loglar:

```text
Robot-head ROS bridge targeting 127.0.0.1:8765
Connected to Raspberry Pi host controller
```

Container ayarında kritik satır:

```yaml
network_mode: host
```

Host network kullanıldığı için `ports:` ekleme.

## 4. Pi üzerindeki ROS node'unu kontrol et

```bash
docker compose -f compose.ros2.yaml exec robot_head_ros bash
```

Container içinde:

```bash
ros2 node list
ros2 topic list
ros2 service list
ros2 topic echo /robot_head/status
```

## 5. Uzak bilgisayar ayarları

Uzak bilgisayarda mümkünse ROS2 Jazzy kullan. Her terminalde:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Aynı değerler Pi'deki `.env` dosyasında bulunmalıdır.

Node görünürlüğünü kontrol et:

```bash
ros2 node list
```

Beklenen node:

```text
/robot_head_ros_bridge
```

## 6. İlk komut testi

ROS moduna geçir:

```bash
ros2 topic pub --once /robot_head/control_mode \
  std_msgs/msg/String "{data: 'ROS'}"
```

Center:

```bash
ros2 topic pub --once /robot_head/center \
  std_msgs/msg/Empty "{}"
```

Thinking yüzü:

```bash
ros2 topic pub --once /robot_head/face \
  std_msgs/msg/String "{data: 'THINKING,5000'}"
```

Oopsie Daisy:

```bash
ros2 topic pub --once /robot_head/oopsie_daisy \
  std_msgs/msg/Empty "{}"
```

Dance:

```bash
ros2 topic pub --once /robot_head/gesture \
  std_msgs/msg/String "{data: 'DANCE,3,7000'}"
```

Pose:

```bash
ros2 topic pub --once /robot_head/pose \
  std_msgs/msg/Float64MultiArray "{data: [100.0, 95.0]}"
```

## 7. Servis örnekleri

```bash
ros2 service call /robot_head/ros_mode_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/center_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/dance_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/greet_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/oopsie_daisy_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/emergency_stop_service std_srvs/srv/Trigger "{}"
```

Trigger servisleri varsayılan config değerlerini kullanır. `count`, `hold_ms`,
metin veya açı gibi parametreli komutlar için topic kullan.

## 8. Durum topic'leri

```text
/robot_head/status             std_msgs/String (JSON)
/robot_head/current_mode       std_msgs/String
/robot_head/bridge_connected   std_msgs/Bool
/robot_head/serial_connected   std_msgs/Bool
```

Örnek:

```bash
ros2 topic echo /robot_head/bridge_connected
ros2 topic echo /robot_head/serial_connected
ros2 topic echo /robot_head/current_mode
ros2 topic echo /robot_head/status
```

## 9. Container yönetimi

Başlat:

```bash
docker compose -f compose.ros2.yaml up -d
```

Durdur:

```bash
docker compose -f compose.ros2.yaml stop
```

Yeniden başlat:

```bash
docker compose -f compose.ros2.yaml restart
```

Kapat ve kaldır:

```bash
docker compose -f compose.ros2.yaml down
```

Kod değiştiğinde yeniden build:

```bash
docker compose -f compose.ros2.yaml up -d --build
```

## 10. Aynı LAN dışında kullanım

`network_mode: host`, container ile Pi arasındaki ağ problemini çözer; farklı
internet bağlantılarındaki iki cihazı kendiliğinden aynı ROS2 ağına getirmez.

Pi ile kontrol bilgisayarı farklı ağlardaysa:

1. Tailscale veya WireGuard gibi bir VPN ile iki cihazı bağla.
2. Multicast discovery VPN üzerinde çalışmıyorsa Fast DDS Discovery Server
   veya statik peer discovery kullan.
3. İki tarafta da aynı `ROS_DOMAIN_ID` ve RMW ayarını kullan.

Discovery Server kullanırken `.env` içine örneğin:

```bash
ROS_DISCOVERY_SERVER=100.64.0.10:11811
```

Sonra:

```bash
docker compose \
  -f compose.ros2.yaml \
  -f compose.ros2.discovery.yaml \
  up -d
```

Uzak bilgisayarda da aynı `ROS_DISCOVERY_SERVER` değişkenini tanımla.

## 11. Sorun giderme

### ROS node görünüyor ama komut çalışmıyor

```bash
ros2 topic echo /robot_head/current_mode
```

Mode `ROS` değilse:

```bash
ros2 service call /robot_head/ros_mode_service std_srvs/srv/Trigger "{}"
```

### Bridge disconnected

Pi OS uygulamasının çalıştığını ve portu dinlediğini kontrol et:

```bash
ss -ltn | grep 8765
```

Container içinden:

```bash
docker compose -f compose.ros2.yaml exec robot_head_ros \
  bash -lc 'nc -zv 127.0.0.1 8765 || true'
```

### Serial disconnected

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

RP2350 seri portunu yalnız Pi OS ana uygulaması açmalıdır. Container'a
`devices:` ile seri port ekleme.

### Aynı LAN'da node discovery yok

İki tarafta:

```bash
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
```

Multicast testi:

Pi container:

```bash
ros2 multicast receive
```

Uzak bilgisayar:

```bash
ros2 multicast send
```

Wi-Fi access point üzerinde AP/client isolation veya multicast engelleme varsa
ROS2 discovery çalışmayabilir.
