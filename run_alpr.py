import argparse, logging, time, yaml, cv2, os
from pipeline import ALPRPipeline, open_stream
from ocr import OCRReader

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",default="config.yaml")
    ap.add_argument("--source",default=None); ap.add_argument("--ocr-backend",default="auto")
    ap.add_argument("--benchmark",action="store_true"); ap.add_argument("--benchmark-seconds",type=int,default=60)
    args=ap.parse_args(); logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    cfg=yaml.safe_load(open(args.config,encoding="utf-8")); source=args.source or cfg["camera"]["source"]
    reader=OCRReader(cfg["models"]["ocr"],args.ocr_backend)
    cap=open_stream(source,cfg["camera"]["reconnect_seconds"]); skip=cfg["camera"].get("frame_skip",0); i=0
    pipe=ALPRPipeline(cfg,reader)
    start=time.time(); frames=0; detections=0; plates=set()
    try:
        import psutil
        proc=psutil.Process(); cpu0=proc.cpu_times()
    except Exception: psutil=None; cpu0=None
    while True:
        ok,frame=cap.read()
        if not ok:
            if os.path.exists(str(source)): break
            cap.release(); cap=open_stream(source,5); continue
        i+=1
        frames+=1
        if skip and i%(skip+1): continue
        events=pipe.process_frame(frame,cfg["camera"]["name"])
        detections += len(events); plates.update(e["plate"] for e in events if e.get("plate"))
        for event in events: logging.info("plate event: %s",event)
        if args.benchmark and time.time()-start >= args.benchmark_seconds: break
        if not args.benchmark and False: break
        if cv2.waitKey(1)&0xff==27: break
    cap.release(); cv2.destroyAllWindows()
    if args.benchmark:
        elapsed=max(time.time()-start,1e-6); fps=frames/elapsed
        cpu="unavailable"
        if psutil and cpu0:
            cpu=f"{(psutil.Process().cpu_times().user-cpu0.user+psutil.Process().cpu_times().system-cpu0.system)/elapsed*100:.1f}%"
        report=f"elapsed_seconds={elapsed:.2f}\naverage_fps={fps:.2f}\ntotal_detections={detections}\nunique_plates={len(plates)}\ncpu_usage={cpu}\n"
        open("benchmark_report.txt","w",encoding="utf-8").write(report); print(report)
if __name__=="__main__": main()
