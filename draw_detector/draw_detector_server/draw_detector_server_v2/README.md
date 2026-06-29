# LittleDaisy Drawing Server — Native Pi Preview

Bu sürümde tablet çizim sayfası tarayıcıda çalışır; Raspberry Pi önizlemesi ise HTML değildir. `python main.py` çalıştırıldığında Pi masaüstünde otomatik olarak bir OpenCV penceresi açılır.

## Çalışma akışı

1. Raspberry Pi üzerinde `python main.py` çalıştırılır.
2. Pi ekranında iki panelli native pencere açılır.
3. Tablet aynı Wi-Fi ağından `http://littledaisy.local:8000` adresine girer.
4. Tablette çizilen ham stroke verileri solda canlı gösterilir.
5. Tablette **Detect & Save** düğmesine basılınca gelen noktalar JSON olarak kaydedilir ve sağ panelde gösterilir.
6. Varsayılan `PROCESSING_MODE = "raw"` olduğundan noktalar sadeleştirilmez veya yumuşatılmaz.

## Proje yapısı

```text
.
├── main.py             # Uvicorn server + native OpenCV preview
├── server.py           # FastAPI / WebSocket / Detect endpoint
├── preview_state.py    # Server ve UI arasındaki thread-safe veri
├── native_preview.py   # Pi ekranındaki iki panelli OpenCV pencere
├── processor.py        # Raw pass-through veya opsiyonel filtreleme
├── config.py
├── requirements.txt
├── static/
│   ├── index.html      # Tablet sayfası
│   ├── app.js          # Canvas, sık nokta toplama, WebSocket
│   └── style.css
└── output/             # Detect sonrası JSON dosyaları
```

## Çalıştırma

Mevcut environment'ı aktif et:

```bash
source /path/to/your/environment/bin/activate
cd draw_detector_v4_native_preview
python main.py
```

Tablet adresi:

```text
http://littledaisy.local:8000
```

IP ile yedek erişim adresi terminalde yazdırılır.

Native pencereyi kapatmak ve server'ı durdurmak için pencere açıkken `Q` veya `ESC` tuşuna bas.

## Bağımlılıklar

`requirements.txt` artık native OpenCV penceresi için GUI destekli OpenCV paketini de içerir:

```text
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.5
opencv-python>=4.9,<5
```

Mevcut environment aktifken bağımlılıkları kur:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Kurulumu doğrula:

```bash
python -c "import cv2; print(cv2.__version__)"
```

Bu projede `cv2.imshow()` kullanıldığı için `opencv-python-headless` yerine GUI destekli `opencv-python` gerekir. Aynı environment içinde birden fazla OpenCV paketi kurulmamalıdır.

## Nokta yoğunluğu

Tablet tarafında iki mekanizma kullanılır:

- `PointerEvent.getCoalescedEvents()` ile tarayıcının birleştirdiği ara stylus/touch örnekleri alınır.
- İki örnek arasında yaklaşık `0.75 px` aralıkla ara noktalar eklenir.

Ayarlar `static/app.js` içindedir:

```javascript
const POINT_SPACING_PX = 0.75;
const MAX_POINTS_PER_STROKE = 50000;
```

Daha da sık nokta için `POINT_SPACING_PX` azaltılabilir; ancak veri boyutu ve robot komut sayısı büyür.

## Detect işlemi

Varsayılan ayar:

```python
PROCESSING_MODE = "raw"
```

Bu modda:

- smoothing uygulanmaz,
- Douglas–Peucker uygulanmaz,
- point sırası korunur,
- yalnızca geçersiz değerler ve tam aynı ardışık noktalar temizlenir.

İleride robot yolu için hafif filtreleme istenirse `config.py` içinde:

```python
PROCESSING_MODE = "filtered"
```

yapılabilir.

## Kaydedilmiş JSON dosyasını ayrı önizleme

Web server'ı açmadan, `Detect & Save` sonrasında oluşan JSON noktalarını ayrı bir OpenCV penceresinde kontrol etmek için:

```bash
python json_preview.py
```

Dosya adı verilmezse `output/` klasöründeki en yeni `drawing_*.json` dosyası açılır. Belirli bir dosyayı açmak için:

```bash
python json_preview.py output/drawing_20260629_123456_789.json
```

Bütün örnek noktaları başlangıçtan itibaren görünür yapmak için:

```bash
python json_preview.py --points
```

Pencere kontrolleri:

```text
P       Her kayıtlı noktayı göster/gizle
L       Noktaları birleştiren çizgileri göster/gizle
R       JSON dosyasını diskten tekrar yükle
N / B   Daha yeni / daha eski JSON dosyasına geç
S       Önizlemeyi PNG olarak kaydet
Q / ESC Kapat
```

Yeşil daire her stroke'un başlangıcını (robot için pen-down başlangıcı), kırmızı daire ise stroke'un sonunu (pen-up noktası) gösterir. Sağ paneldeki `processed_strokes`, sonraki aşamada robot yolu oluşturmak için kullanılacak veri grubudur. Bu normalize noktalar robota doğrudan motor komutu olarak gönderilmeden önce robotun çalışma alanına dönüştürülmeli, sınırları kontrol edilmeli ve hız/ivme planlamasından geçirilmelidir.
