import time, logging, sqlite3
from collections import Counter, deque
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from plate_parser import parse_plate, is_confident_plate
from detection import PlateDetector, crop
from tracking import IOUTracker
from speed import SpeedEstimator
from storage import Storage
from frame_buffer import publish

class ALPRPipeline:
    def __init__(self, cfg, ocr_reader, detector=None):
        self.cfg=cfg; self.ocr=ocr_reader
        d=cfg["models"]; self.detector=detector or PlateDetector(d["detector"],d["confidence"],d["imgsz"],d["device"])
        self.tracker=IOUTracker(); self.speed=SpeedEstimator(cfg["speed"]["pixels_per_meter"])
        self.db_path=Path(__file__).resolve().parent/"k1plak.db"
        storage_root=cfg["storage"]["root"]
        try:
            c=sqlite3.connect(self.db_path)
            row=c.execute("SELECT value FROM settings WHERE key='storage_root'").fetchone()
            if row and row[0]: storage_root=row[0]
            c.close()
        except Exception: pass
        self.storage=Storage(storage_root,cfg["storage"]["jpeg_quality"],
                              cfg["storage"].get("plate_upscale",4),
                              cfg["storage"].get("plate_min_width",640))
        self.last_plate={}; self.last_event_track={}; self.stop_state={}; self.motion_state={}; self.text_history={}
    def process_frame(self, frame, camera_name, timestamp=None, roi=None, camera_id=None):
        original_frame = frame
        roi_offset = (0, 0)
        if roi:
            try:
                polygon = None
                if isinstance(roi, (list, tuple)) and roi and isinstance(roi[0], (list, tuple)):
                    polygon = [(int(p[0]), int(p[1])) for p in roi if len(p) >= 2]
                    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
                    x1,y1,x2,y2 = min(xs),min(ys),max(xs),max(ys)
                else:
                    x1,y1,x2,y2=map(int,roi)
                h,w=frame.shape[:2]
                x1,x2=sorted((max(0,min(w,x1)),max(0,min(w,x2))))
                y1,y2=sorted((max(0,min(h,y1)),max(0,min(h,y2))))
                if x2>x1 and y2>y1:
                    frame=frame[y1:y2,x1:x2]
                    roi_offset=(x1,y1)
                    if polygon and len(polygon) >= 4:
                        mask = np.zeros((y2-y1, x2-x1), dtype="uint8")
                        local_pts = np.array(
                            [[px-x1, py-y1] for px,py in polygon], dtype="int32")
                        cv2.fillPoly(mask, [local_pts], 255)
                        frame = cv2.bitwise_and(frame, frame, mask=mask)
            except Exception:
                logging.warning("invalid ROI ignored: %r",roi)
        timestamp=timestamp or time.time(); detections=self.detector.detect(frame)
        tracks=self.tracker.update(detections,timestamp); events=[]
        for tr in tracks:
            if getattr(tr, "missed", 0):
                continue
            x1,y1,x2,y2=map(int,tr.bbox)
            bw,bh=x2-x1,y2-y1
            if bw < 35 or bh < 10 or bw / max(bh,1) < 1.25 or bw / max(bh,1) > 9.0:
                continue
            plate_crop=crop(frame,tr.bbox)
            if plate_crop.size == 0:
                continue
            # OCR sees a normalized grayscale crop; the original colour crop
            # is still retained for evidence storage.
            try:
                gray=cv2.cvtColor(plate_crop,cv2.COLOR_BGR2GRAY)
                gray=cv2.resize(gray,(max(256,gray.shape[1]*4),max(64,gray.shape[0]*4)),interpolation=cv2.INTER_CUBIC)
                gray=cv2.createCLAHE(2.0,(8,8)).apply(gray)
                ocr_crop=cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)
            except Exception:
                ocr_crop=plate_crop
            text=self.ocr.read(ocr_crop)
            hist=self.text_history.setdefault(tr.track_id,deque(maxlen=5))
            if text: hist.append(str(text))
            # OCR on a tiny/blurred crop can fluctuate; use a short temporal
            # majority before accepting a plate as a traffic event.
            ranked = Counter(hist).most_common(1) if hist else []
            stable_text = ranked[0][0] if ranked else text
            stable_count = ranked[0][1] if ranked else 0
            parsed=parse_plate(stable_text, None, True)
            plate=parsed["plate"]
            previous = self.motion_state.get(tr.track_id)
            current = tr.centers[-1]
            if previous:
                speed=self.speed.kmh(previous[0], current, max(timestamp-previous[1], 1e-3))
            else:
                speed=0.0
            self.motion_state[tr.track_id]=(current,timestamp)
            stopped=bool(previous and speed < 1.0)
            if stopped:
                self.stop_state[tr.track_id]=self.stop_state.get(tr.track_id,timestamp)
                if timestamp-self.stop_state[tr.track_id] >= self.cfg["storage"].get("stopped_after_seconds",10):
                    logging.info("Vehicle %s stopped for %.1f seconds",plate,timestamp-self.stop_state[tr.track_id])
            prev=self.last_plate.get(plate,0)
            track_prev=self.last_event_track.get(tr.track_id,0)
            # Do not pollute traffic records with partial OCR such as "1ز".
            if (stable_count >= 2 and is_confident_plate(parsed)
                    and timestamp-prev>=self.cfg["storage"]["cooldown_seconds"]
                    and timestamp-track_prev>=self.cfg["storage"]["cooldown_seconds"]):
                self.last_plate[plate]=timestamp
                self.last_event_track[tr.track_id]=timestamp
                meta={**parsed,"track_id":tr.track_id,"speed_kmh":round(speed,2),
                      "camera":camera_name,"timestamp":datetime.fromtimestamp(timestamp).isoformat(),
                      "speed_violation":speed>=self.cfg["speed"]["violation_kmh"],
                      "stopped_seconds":round(timestamp-self.stop_state.get(tr.track_id,timestamp),1) if stopped else 0}
                saved=self.storage.save(camera_name,plate,original_frame,plate_crop,meta,datetime.fromtimestamp(timestamp),camera_id)
                meta.update({"vehicle_image":saved["vehicle"],"plate_image":saved["plate"],"metadata_file":saved["meta"]})
                events.append(meta)
                if camera_id is not None:
                    try:
                        c=sqlite3.connect(self.db_path)
                        c.execute("""INSERT INTO detections
                          (plate,category,speed,camera_id,timestamp,vehicle_image,plate_image,violation,stopped_seconds)
                          VALUES(?,?,?,?,?,?,?,?,?)""",
                          (plate,parsed["category"],speed,camera_id,meta["timestamp"],
                           saved["vehicle"],saved["plate"],
                           int(meta["speed_violation"]),meta["stopped_seconds"]))
                        c.commit(); c.close()
                    except Exception: logging.exception("database insert failed")
        annotated=original_frame.copy()
        for d in detections:
            xoff,yoff=roi_offset
            x1,y1,x2,y2=d.bbox
            cv2.rectangle(annotated,(x1+xoff,y1+yoff),(x2+xoff,y2+yoff),(0,255,0),2)
        cv2.putText(annotated, datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    (10,max(25,annotated.shape[0]-12)),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,220,255),2)
        publish(camera_id if camera_id is not None else camera_name, annotated)
        return events

def open_stream(source, reconnect_seconds=5):
    while True:
        cap=cv2.VideoCapture(source)
        if cap.isOpened(): return cap
        cap.release(); logging.error("Unable to open %s; retrying",source); time.sleep(reconnect_seconds)
