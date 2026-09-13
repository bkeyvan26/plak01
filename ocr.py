import logging, json, cv2, numpy as np
from typing import Callable

class OCRReader:
    """Offline OCR adapter. Supply a callable for a project-specific CRNN."""
    def __init__(self, model_path=None, backend="auto", recognizer: Callable = None):
        self.recognizer = recognizer
        self.model = None
        self.backend = backend
        if recognizer is not None: return
        if model_path and backend == "hezar":
            from hezar.models import Model
            self.model = Model.load(model_path)
        elif model_path and str(model_path).lower().endswith((".h5",".keras")):
            try:
                from tensorflow.keras.models import load_model
                self.model = load_model(model_path, compile=False)
                self.backend = "tensorflow"
            except Exception as exc:
                logging.warning("TensorFlow OCR unavailable (%s); OCR disabled", exc)
                self.model = None
        elif model_path and str(model_path).lower().endswith(".onnx"):
            try:
                import onnxruntime as ort
                self.model=ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
                self.labels=json.load(open(str(model_path).replace(".onnx",".labels.json"),encoding="utf-8"))
                self.backend="onnx"
            except Exception as exc:
                logging.warning("ONNX OCR unavailable (%s); OCR disabled", exc); self.model=None
        elif model_path:
            try:
                import torch
                self.model = torch.jit.load(model_path, map_location="cpu")
            except Exception as exc:
                raise RuntimeError("Provide a recognizer callable or a TorchScript/Hezar model") from exc

    def read(self, plate_crop) -> str:
        if self.recognizer: return str(self.recognizer(plate_crop))
        if self.model is None: return ""
        # Hezar accepts file paths; project-specific models should be wrapped
        # through recognizer= to preserve their character-index preprocessing.
        if getattr(self, "backend", None) == "onnx":
            gray=cv2.cvtColor(plate_crop,cv2.COLOR_BGR2GRAY)
            image=cv2.resize(gray,(128,32)).astype("float32")/255.0
            inp=self.model.get_inputs()[0].name
            logits=self.model.run(None,{inp:image[None,None]})[0][0]
            ids=logits.argmax(1); blank=len(self.labels); out=[]; prev=-1
            for idx in ids:
                idx=int(idx)
                if idx!=blank and idx!=prev and idx<len(self.labels): out.append(self.labels[idx])
                prev=idx
            return "".join(out)
        return ""
