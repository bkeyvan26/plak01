"""Unified launcher: daemon camera workers plus Flask in the main thread."""
from __future__ import annotations
import logging, sqlite3, threading, time, copy, json
import cv2, yaml
from webapp import app, db, DB_PATH
from pipeline import ALPRPipeline
from ocr import OCRReader

STOP=threading.Event(); STATUS={}
def syslog(level,message,camera_id=None):
    logging.log(getattr(logging,level.upper(),logging.INFO),message)
    try:
        c=sqlite3.connect(DB_PATH); c.execute("INSERT INTO system_logs(level,message,camera_id) VALUES(?,?,?)",(level.upper(),message,camera_id)); c.commit(); c.close()
    except Exception: logging.exception("system log insert failed")
def camera_urls(row):
    auth=f"{row['username']}:{row['password']}@" if row["username"] else ""
    base=f"rtsp://{auth}{row['ip']}:{row['port']}"
    configured=(row["source"] if "source" in row.keys() else "") if row else ""
    if not configured and row["ip"] == "172.20.34.112":
        configured="rtsp://root:123456@172.20.34.112:554/axis-media/media.amp"
    return [configured] if configured else [base+"/axis-media/media.amp",base+"/axis-media/media.a",base+"/Streaming/Channels/101",base+"/"]
def parse_roi(value):
    if not value:return None
    try:
        if str(value).strip().startswith("{"):
            data=json.loads(value)
            pts=data.get("points",[])
            if not pts:
                shapes=data.get("shapes",[])
                if shapes:
                    pts=shapes[0].get("points",[])
            if len(pts) >= 4:
                return [(int(p[0]), int(p[1])) for p in pts]
            return None
        parts=tuple(int(float(x.strip())) for x in str(value).split(","))
        return parts if len(parts)==4 else None
    except Exception:return None
def worker(row,cfg):
    cid,name=row["id"],row["name"]; STATUS[cid]={"online":False,"fps":0.0,"last_detection":None}
    local_cfg=copy.deepcopy(cfg)
    local_cfg["speed"]["violation_kmh"]=float(row["speed_threshold"] or cfg["speed"]["violation_kmh"])
    try: pipe=ALPRPipeline(local_cfg,OCRReader(local_cfg["models"]["ocr"],"auto"))
    except Exception as exc: syslog("ERROR",f"camera {name}: model initialization failed: {exc}",cid); return
    failures=0
    while not STOP.is_set() and failures<3:
        cap=None
        for url in camera_urls(row):
            candidate=cv2.VideoCapture(url)
            if candidate.isOpened(): cap=candidate; break
            candidate.release()
        if cap is None:
            failures+=1; syslog("ERROR",f"camera {name}: RTSP connection failed ({failures}/3)",cid)
            if cap: cap.release()
            STOP.wait(5*(2**(failures-1))); continue
        failures=0; STATUS[cid]["online"]=True; syslog("INFO",f"camera {name} online",cid)
        frames=0; started=time.time()
        while not STOP.is_set():
            ok,frame=cap.read()
            if not ok: STATUS[cid]["online"]=False; syslog("WARNING",f"camera {name}: stream lost",cid); break
            frames+=1; skip=int(cfg["camera"].get("frame_skip",0))
            if skip and frames%(skip+1): continue
            events=pipe.process_frame(frame,name,roi=parse_roi(row["zone"]),camera_id=cid)
            if events: STATUS[cid]["last_detection"]=events[-1].get("plate")
            STATUS[cid]["fps"]=frames/max(time.time()-started,1e-3)
        cap.release()
    STATUS[cid]["online"]=False
    if failures>=3: syslog("ERROR",f"camera {name} marked offline after 3 failed attempts",cid)
def main():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    cfg=yaml.safe_load(open("config.yaml",encoding="utf-8")); db(); c=db()
    rows=c.execute("SELECT * FROM cameras WHERE enabled=1").fetchall(); c.close()
    threads=[threading.Thread(target=worker,args=(r,cfg),daemon=True,name=f"camera-{r['id']}") for r in rows]
    for t in threads:t.start()
    try: app.run(host="0.0.0.0",port=5000,threaded=True)
    except (KeyboardInterrupt,SystemExit): pass
    finally:
        STOP.set()
        for t in threads:t.join(timeout=3)
        syslog("INFO","k1plak shutdown complete")
if __name__=="__main__": main()
