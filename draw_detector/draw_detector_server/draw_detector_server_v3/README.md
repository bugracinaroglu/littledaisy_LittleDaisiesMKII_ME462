# LittleDaisy Drawing Server — Bottom-left Coordinates and Robot Jobs

Bu sürümde tablet tarayıcıda çizim yapar; Raspberry Pi üzerinde `main.py` çalıştırıldığında üç panelli native OpenCV penceresi açılır.

```text
LIVE TABLET | LAST DETECTED | ROBOT JOB
```

## Temel davranış

- Sol panel, tabletteki mevcut çizimi gerçek zamanlı gösterir.
- **Detect & Save**, o anda canvas üzerinde bulunan bütün çizimin tam snapshot'ını `output/` içine kaydeder.
- Detectler arasında eklenen veya silinen ara durumlar robot comparison state'ini değiştirmez.
- Orta panel yalnızca son Detect snapshot'ını gösterir.
- Terminalde `send_data2robot_arm` yazılınca son Detect snapshot'ı, robotun son başarıyla commit edilmiş çizimiyle karşılaştırılır.
- Sağ panel yalnızca bu komut sonrasında oluşan `erase`, `draw`, `same` veya `erase_all` planını gösterir.
- Aynı Detect snapshot'ı ikinci kez gönderilmeye çalışılırsa yeni job oluşturulmaz.

## Koordinat sistemi

Tablet HTML canvas verisi doğal olarak sol-üst orijinlidir. Detect sırasında server bunu bir kez dönüştürür:

```python
x_output = x_canvas
y_output = 1.0 - y_canvas
```

Bütün `output/*.json`, `comparison_state` ve `robot_jobs` verileri şu sistemi kullanır:

```text
          +Y
           ↑
           |
(0,0) -----+------→ +X
```

- Sol alt: `[0.0, 0.0]`
- Sağ alt: `[1.0, 0.0]`
- Sol üst: `[0.0, 1.0]`
- Sağ üst: `[1.0, 1.0]`

## Output snapshot

Her Detect ayrı timestamp'li dosya üretir. Eski dosyalar değiştirilmez:

```text
output/
├── drawing_....json
└── drawing_....json
```

Output JSON yalnız processing sonucunu tutar:

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

`PROCESSING_MODE = "raw"` olduğu için geçerli noktalar ve sıraları korunur. Ayrı `raw_strokes` kopyası kaydedilmez.

Boş canvas için de Detect yapılabilir. Boş snapshot daha sonra committed çizime karşı `erase` job'ları üretebilir.

## Silme işlemi ve stroke ID

Her yeni kalem stroke'u kalıcı bir `stroke_id` alır.

- **Stroke Eraser:** Stroke canvas'tan çıkar. Committed durumda bulunuyorsa sonraki difference job'ında `erase` olur.
- **Pixel Eraser:** Değiştirilen eski stroke artık yeni snapshot'ta bulunmaz. Kalan parçalar yeni ID'li stroke'lar olur ve eski ID `parent_stroke_id` olarak saklanır.

Bunun job karşılığı:

```text
eski stroke   → erase
kalan parçalar → draw
```

Bu yaklaşım, bir stroke'un noktalarını sessizce değiştirip hangi kısmın silindiğini belirsiz bırakmaz.

## Comparison state

```text
comparison_state/robot_committed_state.json
```

Bu dosya son Detect'i değil, robotun başarıyla kabul ettiği son çizimi temsil eder. Detect'e basmak bu dosyayı değiştirmez.

Şimdilik fiziksel robot bağlantısı yerine `SIMULATE_ROBOT_ACK = True` kullanılır. `send_data2robot_arm` başarılı simülasyondan sonra state'i commit eder. Gerçek robot eklendiğinde state yalnız gerçek ACK sonrasında güncellenmelidir.

## Robot job modları

Terminal komutları:

```text
set_mode difference
set_mode full_redraw
send_data2robot_arm
show_state
```

### Difference

```text
eski var, yeni yok → erase
yeni var, eski yok → draw
ID ve geometri aynı → same
aynı ID, geometri değişmiş → erase old + draw new
```

`same` log ve preview içindir; fiziksel robota hareket olarak gönderilmez.

### Full redraw

```text
erase_all
bütün güncel stroke'ları draw
```

## Çalıştırma

```bash
source /path/to/environment/bin/activate
cd draw_detector_v5_robot_jobs
python -m pip install -r requirements.txt
python main.py
```

Tablet:

```text
http://littledaisy.local:8000
```

## JSON preview

```bash
python json_preview.py
python json_preview.py --points
python json_preview.py output/drawing_....json
```

## Testler

```bash
python -m unittest discover -s tests -v
```

Testler sol-alt dönüşümü, raw point korumasını, stroke silme, pixel eraser sonrası segment değiştirme ve full redraw planını kontrol eder.
