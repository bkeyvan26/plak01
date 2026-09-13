from dataclasses import dataclass
from typing import List, Optional
import logging

@dataclass
class Detection:
    bbox: tuple
    confidence: float
    class_name: str = "vehicle"

class PlateDetector:
    """Ultralytics wrapper; accepts .pt, ONNX and NCNN model directories."""
    def __init__(self, model_path: str, confidence: float = .35, imgsz: int = 640, device: str = "cpu"):
        self.confidence, self.imgsz, self.device = confidence, imgsz, device
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            logging.warning("ultralytics unavailable; detector disabled")
            self.model = None
            return
        try:
            self.model = YOLO(model_path)
        except Exception as exc:
            logging.warning("detector model unavailable (%s); live capture will continue without detection", exc)
            self.model = None

    def detect(self, frame) -> List[Detection]:
        if self.model is None:
            return []
        results = self.model.predict(frame, conf=self.confidence, imgsz=self.imgsz,
                                     device=self.device, verbose=False)
        out = []
        for r in results:
            names = getattr(r, "names", {})
            if r.boxes is None: continue
            for box in r.boxes:
                xyxy = box.xyxy[0].tolist()
                cls = int(box.cls[0]) if box.cls is not None else 0
                out.append(Detection(tuple(map(int, xyxy)), float(box.conf[0]),
                                     names.get(cls, "plate")))
        return out

def crop(frame, bbox):
    h, w = frame.shape[:2]
    x1,y1,x2,y2 = map(int, bbox)
    return frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
