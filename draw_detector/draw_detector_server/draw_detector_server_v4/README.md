# LittleDaisy Drawing Server — Startup Reset and Robot Jobs

Bu sürümde tablet tarayıcıda çizim yapar; Raspberry Pi üzerinde `main.py`
çalıştırıldığında üç panelli native OpenCV penceresi açılır:

```text
LIVE TABLET | LAST DETECTED | ROBOT JOB
```

## Program başlangıcında ne olur?

Her `python main.py` çalıştırılışında:

- `output/` içindeki timestamp'li Detect snapshot'ları **korunur**.
- `comparison_state/` içindeki eski JSON dosyaları silinir.
- `robot_jobs/` içindeki eski JSON dosyaları silinir.
- Sol, orta ve sağ preview panellerinin runtime state'i sıfırlanır.
- Önceki çalıştırmadaki output dosyaları aktif hedef olarak seçilmez.
- Bu çalıştırmada yeniden **Detect** yapılmadan `send_data2robot_arm` çalışmaz.

Böylece output çizim arşivi olarak kalır fakat eski bir çizimin yanlışlıkla
robota gönderilmesi önlenir.

## Başlangıç full erase ayarı

`config.py`:

```python
STARTUP_FULL_ERASE_ENABLED = True
```

`True` olduğunda program başlangıcında aşağıdaki path içermeyen job otomatik
oluşturulur ve robot transport katmanına gönderilir:

```json
{
  "mode": "full_erase",
  "actions": [
    {"type": "erase_all"}
  ]
}
```

Bu projede full-clean hareket yolu tanımlanmaz. Gelecekte robot kontrol kodu
`erase_all` komutunu alınca kendi temizleme yolunu uygulamalıdır.

- Startup erase ACK alırsa robot yüzeyi boş kabul edilir ve çizim gönderimi açılır.
- Startup erase başarısız olursa `send_data2robot_arm` engellenir; fiziksel yüzey
  durumu bilinmiyorken boş comparison state üzerinden çizim gönderilmez.
- `STARTUP_FULL_ERASE_ENABLED = False` yapılırsa başlangıçta erase job üretilmez.
  Bu durumda fiziksel yüzeyin gerçekten boş olduğundan kullanıcı sorumludur.

Şimdilik:

```python
SIMULATE_ROBOT_ACK = True
```

olduğu için ACK simüle edilir.

## Detect davranışı

**Detect & Save**, o anda tablet canvas'ında bulunan çizimin tamamını yeni bir
snapshot olarak kaydeder:

```text
output/drawing_YYYYMMDD_HHMMSS_mmm.json
```

Örnek:

```text
Detect 1 -> U
Detect 2 -> U + yeni çizgi
Detect 3 -> silme sonrası güncel tam çizim
```

Her dosya bağımsızdır; eski output dosyaları değiştirilmez. Detect işlemi
comparison state'i değiştirmez ve robot job oluşturmaz.

## Koordinat sistemi

Tablet HTML canvas verisi sol-üst orijinlidir. Detect sırasında bir kez:

```python
x_output = x_canvas
y_output = 1.0 - y_canvas
```

dönüşümü uygulanır. Output, comparison ve robot job verileri sol-alt orijinlidir:

```text
          +Y
           ↑
           |
(0,0) -----+------→ +X
```

## Output JSON

Output içinde yalnız processing sonucu tutulur. `PROCESSING_MODE = "raw"`
olduğu için şimdilik tabletin geçerli noktaları, sırası ve stroke ID'leri korunur:

```json
{
  "drawing_id": "drawing_...",
  "coordinate_system": "normalized_bottom_left_origin",
  "processing": {
    "mode": "raw",
    "smoothing_passes": 0,
    "simplify_epsilon": 0.0002
  },
  "strokes": [
    {
      "stroke_id": "...",
      "points": [[0.2, 0.7], [0.21, 0.69]]
    }
  ]
}
```

## Difference ve silme mantığı

Comparison yalnız terminalde `send_data2robot_arm` yazıldığında yapılır.
Karşılaştırılanlar:

```text
boş veya son ACK edilmiş robot state
                ↕
bu program çalıştırmasındaki son Detect snapshot'ı
```

- Eski state'te var, yeni çizimde yok: `erase`
- Yeni çizimde var, eskide yok: `draw`
- Aynı ID ve aynı geometri: `same`
- Aynı ID ama değişmiş geometri: `erase old + draw new`
- Pixel eraser stroke'u bölerse: eski stroke `erase`, yeni segmentler `draw`

`same` yalnız log/preview içindir; robota hareket komutu olarak gönderilmesi gerekmez.

## Robot job modları

```text
set_mode difference
set_mode full_redraw
```

### Difference

Yalnız değişiklikler için `erase`, `draw`, `same` action'ları üretir.

### Full redraw

```text
erase_all
bütün son Detect stroke'larını draw
```

Buradaki `erase_all` için de temizleme yolu robot kontrol katmanına aittir.

## Terminal komutları

```text
send_data2robot_arm
send_full_erase
set_mode difference
set_mode full_redraw
show_state
help
```

`send_full_erase`, program çalışırken bağımsız bir `erase_all` job'u üretir. ACK
sonrasında comparison state tekrar boş kabul edilir.

## Çalıştırma

```bash
source /path/to/environment/bin/activate
cd draw_detector_v6_startup_state
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

Testler ayrıca şunları doğrular:

- Sol-alt koordinat dönüşümü
- Raw point ve stroke ID koruması
- Difference ve pixel eraser davranışı
- Path içermeyen `erase_all`
- Startup sırasında output'un korunması
- Comparison/job JSON dosyalarının temizlenmesi
- Yeni Detect yapılmadan eski output'un aktif hedef sayılmaması
