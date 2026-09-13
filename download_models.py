"""Download the pinned public model artifacts used by k1plak.

The repositories expose artifacts in-tree rather than GitHub Releases:
the detector is an NCNN directory and the OCR repository contains OCR_inference.h5.
"""
from __future__ import annotations
import argparse, hashlib, logging, time
from pathlib import Path
import requests

ROOT = "https://huggingface.co/Dibachain/Platrix/resolve/main/"
DETECTOR = {
    "plate_yolo.onnx": ROOT+"plate_yolo.onnx?download=true",
    "plate_yolo_fallback.onnx": ROOT+"plate_yolo_fallback.onnx?download=true",
}
OCR = {
    "ocr_crnn.onnx": ROOT+"ocr_crnn.onnx?download=true",
    "ocr_crnn.labels.json": ROOT+"ocr_crnn.labels.json?download=true",
    "ocr_cnn.onnx": ROOT+"ocr_cnn.onnx?download=true",
    "ocr_cnn.labels.json": ROOT+"ocr_cnn.labels.json?download=true",
}

def fetch(url, destination, retries=3, timeout=60):
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries+1):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                tmp=destination.with_suffix(destination.suffix+".part")
                with open(tmp,"wb") as f:
                    for chunk in r.iter_content(1024*1024):
                        if chunk: f.write(chunk)
                if tmp.stat().st_size < 32: raise IOError("downloaded file is unexpectedly small")
                tmp.replace(destination)
                digest=hashlib.sha256(destination.read_bytes()).hexdigest()
                logging.info("%s: %d bytes sha256=%s", destination, destination.stat().st_size, digest)
                return True
        except Exception as exc:
            logging.warning("download attempt %d/%d failed for %s: %s",attempt,retries,url,exc)
            if attempt < retries: time.sleep(2**attempt)
    return False

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="models")
    args=ap.parse_args(); root=Path(args.root); ok=True
    for name,url in DETECTOR.items(): ok &= fetch(url,root/"platrix"/name)
    for name,url in OCR.items(): ok &= fetch(url,root/"platrix"/name)
    if not ok:
        raise SystemExit("One or more artifacts failed; rerun after checking network/GitHub availability.")
    print(f"Models downloaded and verified under {root.resolve()}")
if __name__=="__main__": logging.basicConfig(level=logging.INFO); main()
