# LittleDaisy — Draw Server

Tablet üzerinde HTML canvas'a çizilen stroke'ları Raspberry Pi'ye gönderen,
processor'dan geçirip JSON olarak kaydeden basit bir yerel sunucu.

İleride bu JSON, robot kol için pen-up/down hareket sırasına dönüştürülecek.

## Yapı

```
draw_server/
├── main.py             ← çalıştırılan dosya
├── server.py           ← FastAPI endpoint'leri
├── processor.py        ← smoothing + Douglas-Peucker + tiny filter
├── config.py           ← tüm tunable parametreler
├── requirements.txt
├── static/
│   ├── index.html      ← tablet sayfası
│   ├── app.js          ← canvas + pointer event'leri
│   └── style.css
└── output/             ← drawing_TIMESTAMP.json dosyaları
```

## Kurulum

Pi üzerinde (bir kez):

```bash
cd draw_server
pip install -r requirements.txt
```

## Çalıştırma

```bash
python main.py
```

Başlangıçta sunucu kendi IP'sini ve hostname'ini yazar.

Tablet'ten (aynı Wi-Fi'da) tarayıcıyı aç:

- `http://littledaisy.local:8000`  (iOS Safari'de çalışır)
- veya `http://<pi-ip>:8000`         (her cihazda çalışır)

## Kullanım

- **Pen** — çizim moduna geç
- **Stroke Eraser** — dokunulan tüm stroke'u siler
- **Pixel Eraser** — silginin geçtiği yerdeki pikselleri siler, stroke
  gerekirse ikiye bölünür
- **Clear** — her şeyi sil
- **Detect & Save** — stroke'ları Pi'ye yollar, processor uygular,
  JSON kaydeder

## Çıktı formatı

```json
{
  "timestamp": "20260629_123914",
  "canvas_size_px": 500,
  "canvas_aspect": [1, 1],
  "coordinate_system": "normalized_top_left_origin",
  "processed_strokes": [
    { "points": [[x, y], [x, y], ...] }
  ],
  "raw_strokes": [...]
}
```

- `x, y` ∈ [0, 1], **sol üst köşe = (0, 0)** (HTML canvas konvansiyonu).
- Robot kol koordinat sistemine (örn. sol alt = (0,0), mm cinsinden)
  dönüşüm ileride ayrı bir `transformer` modülünde yapılacak.

## Parametre ayarı

Hepsi `config.py`'da:

- `SMOOTHING_PASSES`   — 0 = smoothing kapalı, 1-2 = hafif yumuşatma
- `SIMPLIFY_EPSILON`   — Douglas-Peucker epsilon (normalize, 0..1).
                         Küçült: daha çok nokta. Büyüt: daha aza indirir.
- `MIN_STROKE_POINTS`  — bu sayıdan az noktalı stroke atılır
- `MIN_STROKE_LENGTH`  — bu uzunluktan kısa stroke atılır (normalize)
- `SAVE_RAW_STROKES`   — False yaparsan JSON'da sadece processed kalır

## Sonraki adımlar

1. `transformer.py` — normalize → mm robot koordinatı
2. `robot_io.py`    — ROS publisher (veya serial)
3. Ana `littledaisy_LittleDaisiesMKII_ME462` projesine entegrasyon
