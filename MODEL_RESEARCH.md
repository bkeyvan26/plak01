# k1plak open-source model research (2026-08-30)

## Detection candidates

| Candidate | What is available | CPU expectation on i5-9400F* | Recommendation |
|---|---|---:|---|
| `shahriar-hd/FarsiPlateRecognition` (YOLOv8 plate detector; optional NCNN export) | Iranian end-to-end project; repository documents `best.pt` and `yolo export ... format=ncnn` | YOLOv8n/NCNN typically ~25–60 ms per 640px frame (17–40 FPS), depending on resolution and threads | **Best starting point for CPU deployment**; benchmark its supplied weights |
| `RezaGooner/Multi-Task-Iranian-Vehicle-Monitoring-System` (YOLO11 plate + character detectors) | MIT-licensed Iranian system with plate and character detection and city lookup | YOLO11n/CPU ~35–70 ms (14–28 FPS); larger variants slower | Best if character boxes are desired, but verify weight files and latency |
| `barzansaeedpour/ANPR-YOLOv8` (YOLOv8 training project) | Iranian ANPR training code; README trains `yolov8m.pt` at `imgsz=300` | YOLOv8m CPU often ~80–160 ms (6–12 FPS) | Useful training baseline, not the first choice for a 15-FPS CPU target |
| `alitourani/yolo-license-plate-detection` (YOLOv3) | Iranian plate detector and downloadable/split weights | YOLOv3-tiny can exceed 15 FPS; full YOLOv3 usually cannot | Legacy fallback only |

`*` These are engineering estimates, not measurements published by the repositories. Measure with the exact image size, OpenCV/PyTorch or NCNN backend, and number of CPU threads used in production.

### Detector installation

Recommended initial path:

```powershell
git clone https://github.com/shahriar-hd/FarsiPlateRecognition
cd FarsiPlateRecognition
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install ultralytics opencv-python
# Optional CPU-oriented export:
yolo export model=best.pt format=ncnn imgsz=640
```

Alternative repositories:

```powershell
git clone https://github.com/RezaGooner/Multi-Task-Iranian-Vehicle-Monitoring-System
git clone https://github.com/barzansaeedpour/ANPR-YOLOv8
git clone https://github.com/alitourani/yolo-license-plate-detection
```

## OCR candidates

| Candidate | Type/domain | Published accuracy evidence | CPU/offline suitability |
|---|---|---|---|
| `hezarai/crnn-base-fa-v2` | CRNN Persian text recognizer | Model card does **not** report plate accuracy; the related card warns that the base model is weak on digits | Easy offline loading with `hezar`; fine-tune on plate crops before use |
| `mahdimtd/persian-plate-recognition` | TensorFlow CRNN explicitly specialized for Persian plates | Repository describes a custom CRNN but gives no independently reproducible 98%+ metric | Strongest direct plate-domain starting point if weights are present |
| `Arashkazemii/Persian-License-Plate-Recognition-System` | Custom OCR model (`best ocr.pt`) plus YOLOv5 detector | Repository claims robust/high-accuracy behavior but provides no formal test-set percentage | Offline PyTorch; inspect model files and label map |

No reviewed open checkpoint provides a verifiable, public **98%+ full-plate accuracy** on a representative Iranian test set. `hezarai/crnn-base-fa-v1` explicitly says it is optimized for scanned documents and does not recognize numbers/digits properly; therefore it should not be used unchanged for plates. The realistic route to a 98% target is a plate-specific CRNN/CTC model fine-tuned on Iranian plate crops (for example, Iranis-derived data), with separate validation for each plate category.

### OCR installation

General CRNN baseline:

```powershell
pip install hezar torch torchvision opencv-python pillow
```

```python
from hezar.models import Model
ocr = Model.load("hezarai/crnn-base-fa-v2")
print(ocr.predict(["plate_crop.png"]))
```

Plate-specialized repositories:

```powershell
git clone https://github.com/mahdimtd/persian-plate-recognition
git clone https://github.com/Arashkazemii/Persian-License-Plate-Recognition-System
```

Expect to install each repository's `requirements.txt`, then load its supplied CRNN/OCR checkpoint. Preserve the repository's character-index mapping; Persian letters must not be alphabetically re-indexed.

## Final recommendation

1. Detector: start with `FarsiPlateRecognition`'s Iranian YOLOv8 weights; export to NCNN or use a small Ultralytics model at 320–640 px and benchmark on the i5-9400F.
2. OCR: use a plate-specific CRNN from `mahdimtd` or `Arashkazemii` if its checkpoint and mapping are complete. Use Hezar only as a fine-tuning baseline, not as a ready-to-deploy plate reader.
3. Validate by category (private, taxi, public, agricultural, government, temporary, motorcycle), by day/night, and by full-plate exact match—not only per-character accuracy.
