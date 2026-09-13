"""Offline end-to-end registration test with fake detector/OCR."""
from pathlib import Path
import sys, cv2, numpy as np, yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from detection import Detection
from pipeline import ALPRPipeline
from ocr import OCRReader

class FakeDetector:
    def detect(self, frame): return [Detection((80,80,560,260),.99,"plate")]
def main():
    root=Path(__file__).resolve().parents[1]; cfg=yaml.safe_load((root/"config.yaml").read_text())
    cfg["storage"]["root"]=str(root/"storage")
    cfg["storage"]["cooldown_seconds"]=0
    frame=np.zeros((360,640,3),np.uint8); cv2.rectangle(frame,(80,80),(560,260),(80,80,80),-1)
    pipe=ALPRPipeline(cfg,OCRReader(recognizer=lambda crop:"12?34520"),detector=FakeDetector())
    events=pipe.process_frame(frame,"synthetic_camera",camera_id=1)
    print("events:",repr(events).encode("ascii","backslashreplace").decode())
    print("storage root:",Path(cfg["storage"]["root"]).resolve())
if __name__=="__main__": main()
