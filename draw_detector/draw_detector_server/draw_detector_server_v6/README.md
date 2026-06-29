# LittleDaisy Drawing Server — Timestamped Jobs + latest_job Queue

Tablet, Raspberry Pi üzerindeki yerel HTML çizim sayfasına bağlanır. `main.py`
çalıştığında Raspberry Pi masaüstünde üç panelli OpenCV penceresi açılır:

```text
LIVE TABLET | LAST DETECTED | ROBOT JOB
```

## Başlangıç ayarları

`config.py`:

```python
STARTUP_OUTPUT_ERASE_ENABLED = False
RESET_COMPARISON_STATE_ON_START = True
RESET_ROBOT_JOBS_ON_START = True
STARTUP_FULL_ERASE_ENABLED = True
```

- `output/`, `STARTUP_OUTPUT_ERASE_ENABLED=False` iken korunur.
- Ayar `True` ise yalnız `output/*.json` başlangıçta silinir.
- Comparison state ve eski robot job JSON'ları başlangıçta temizlenir.
- Eski output arşivde kalsa bile bu program çalıştırmasında yeniden **Detect**
  yapılmadan robota veri gönderilemez.
- Startup full erase açıksa queue'ya ilk olarak path içermeyen `erase_all` işi eklenir.
  Fiziksel temizleme rotasını robot controller tanımlar.

## Detect davranışı

Her **Detect & Save**, canvas üzerindeki güncel çizimin tamamını timestamp'li bir
snapshot olarak kaydeder:

```text
output/drawing_YYYYMMDD_HHMMSS_mmm.json
```

Detect comparison yapmaz ve robot job üretmez. Output JSON yalnız `strokes`
alanını taşır. `PROCESSING_MODE="raw"` olduğu sürece bu noktalar tablet verisiyle
aynıdır.

## Koordinat sistemi

Output, comparison ve robot action noktalarında orijin sol alttadır:

```text
          +Y
           ↑
           |
(0,0) -----+------→ +X
```

HTML canvas'tan gelen Y koordinatı Detect sırasında bir kez çevrilir:

```python
y_output = 1.0 - y_canvas
```

## Robot job dosyaları ve latest_job.json

Her robot görevi yalnızca bir kez, ayrı timestamp'li JSON dosyası olarak saklanır:

```text
robot_jobs/
├── jobs/
│   ├── job_20260629_203538_489123_full_erase.json
│   ├── job_20260629_203540_102450_difference.json
│   └── job_20260629_203541_884010_full_redraw.json
└── latest_job.json
```

Timestamp'li job dosyası gerçek executable veriyi taşır:

```json
{
  "job_id": "job_20260629_203540_102450_difference",
  "mode": "difference",
  "status": "completed",
  "coordinate_system": "normalized_bottom_left_origin",
  "actions": [
    {
      "type": "draw",
      "stroke_id": "stroke-001",
      "points": [[0.1, 0.2], [0.2, 0.3]]
    }
  ]
}
```

`latest_job.json` ise bu büyük point verilerini tekrar etmez. Job dosyalarını
oluşturulma sırasıyla listeleyen küçük bir queue manifest'idir:

```json
{
  "schema_version": 1,
  "updated_at": "2026-06-29T20:35:42.100+03:00",
  "active_job_id": null,
  "last_completed_job_id": "job_20260629_203540_102450_difference",
  "queue": [
    {
      "sequence": 1,
      "job_id": "job_20260629_203538_489123_full_erase",
      "job_file": "jobs/job_20260629_203538_489123_full_erase.json",
      "mode": "full_erase",
      "status": "completed"
    },
    {
      "sequence": 2,
      "job_id": "job_20260629_203540_102450_difference",
      "job_file": "jobs/job_20260629_203540_102450_difference.json",
      "mode": "difference",
      "status": "completed"
    }
  ]
}
```

Bu yapıda:

- `jobs/job_...json`: robota gönderilecek gerçek action ve point verisi.
- `latest_job.json`: job sırası, dosya referansı ve durum bilgisi.
- Aynı point dizileri iki dosyada tutulmaz.
- ROS node, önce `latest_job.json` manifest'ini okuyabilir/publish edebilir; ardından
  sıradaki `job_file` içeriğini ayrı bir topic veya service üzerinden işleyebilir.

## Queue ve comparison zamanı

`send_data2robot_arm` yazıldığında timestamp'li bir job isteği oluşturulur ve
`latest_job.json` queue'suna eklenir. Difference hesabı hemen yapılmaz. Sırası
geldiğinde:

```text
son başarıyla committed edilmiş robot state
                    ↕
job'un referans verdiği Detect snapshot'ı
```

karşılaştırılır. Böylece art arda birkaç görev eklenirse ikinci görev, ilk görev
başarıyla tamamlandıktan sonraki committed state'e göre hazırlanır.

- Eski state'te var, yeni çizimde yok: `erase`
- Yeni çizimde var, eskide yok: `draw`
- Aynı ID ve aynı geometri: `same`
- Değişmiş stroke: `erase old + draw new`
- Pixel eraser stroke'u bölerse: eski stroke `erase`, yeni segmentler `draw`

`same` preview/log içindir; robot hareket katmanı bunu yok sayabilir.

## Job durumları

Timestamp'li job dosyasının ve manifest entry'sinin durumu sırayla değişir:

```text
pending → processing → completed
                      ↘ failed
```

Robot ACK verirse hedef drawing:

```text
comparison_state/robot_committed_state.json
```

 içine committed edilir. Job başarısız olursa comparison state değiştirilmez.

Yüzey durumu bilinmiyorsa drawing job'ları bekler; queue'daki bir `full_erase`
güvenlik amacıyla önce işlenebilir. Başarılı erase sonrasında normal sıra devam eder.

Şimdilik:

```python
SIMULATE_ROBOT_ACK = True
```

olduğu için robot ACK'i simüle edilir.

## Job modları

```text
set_mode difference
set_mode full_redraw
```

- `difference`: `erase`, `draw`, `same` üretir.
- `full_redraw`: `erase_all` ve güncel bütün stroke'lar için `draw` üretir.
- `send_full_erase`: yalnız `{"type": "erase_all"}` içeren job ekler.

## Terminal komutları

```text
send_data2robot_arm
send_full_erase
set_mode difference
set_mode full_redraw
show_state
show_queue
help
```

`show_state` ve `show_queue`; pending, processing, completed ve failed sayılarını,
aktif job'u ve committed drawing ID'sini gösterir.

## Çalıştırma

```bash
source /path/to/environment/bin/activate
cd draw_detector_v10_latest_queue_manifest
python -m pip install -r requirements.txt
python main.py
```

Tablet:

```text
http://littledaisy.local:8000
```

## Testler

```bash
python -m unittest discover -s tests -v
```

Testler; sol-alt koordinat dönüşümü, stroke silme/difference davranışı, startup
temizliği, timestamp'li job dosyaları, `latest_job.json` manifest sırası, deferred
comparison, FIFO işleme ve startup full erase güvenlik davranışını doğrular.
