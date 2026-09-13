import argparse, logging, time, yaml, cv2
from pipeline import ALPRPipeline, open_stream
from ocr import OCRReader

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",default="config.yaml"); ap.add_argument("--seconds",type=int,default=30)
    args=ap.parse_args(); logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    cfg=yaml.safe_load(open(args.config,encoding="utf-8"))
    source="rtsp://root:123456@172.20.34.112:554/"
    cap=open_stream(source,cfg["camera"]["reconnect_seconds"]); pipe=ALPRPipeline(cfg,OCRReader(cfg["models"]["ocr"]))
    start=time.time(); frames=0; events=0; sample=None
    while time.time()-start < args.seconds:
        ok,frame=cap.read()
        if not ok: logging.error("RTSP read failed"); break
        frames+=1
        found=pipe.process_frame(frame,cfg["camera"]["name"])
        for event in found:
            events+=1; logging.info("plate=%s speed=%.2f timestamp=%s",event["plate"],event["speed_kmh"],event["timestamp"])
            sample=event
    cap.release()
    if not events: print("No detections. Check RTSP URL/credentials, model paths, detector confidence, lighting, and OCR adapter.")
    else: print(f"Captured {events} events from {frames} frames; sample files are in {cfg['storage']['root']}.")
if __name__=="__main__": main()
