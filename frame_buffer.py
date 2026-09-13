import threading, time, cv2
_frames={}; _lock=threading.RLock()
def publish(camera_key, frame):
    if isinstance(frame,(bytes,bytearray)): data=bytes(frame)
    else:
        ok,encoded=cv2.imencode(".jpg",frame,[cv2.IMWRITE_JPEG_QUALITY,80])
        if not ok:return
        data=encoded.tobytes()
    with _lock: _frames[str(camera_key)]=(data,time.time())
def get(camera_key, max_age=5):
    with _lock:
        row=_frames.get(str(camera_key))
        if not row:return None
        return row if time.time()-row[1] <= max_age else None
def placeholder(name):
    import numpy as np
    img=np.zeros((360,640,3),dtype=np.uint8); cv2.putText(img,f"No Signal: {name}",(150,180),cv2.FONT_HERSHEY_SIMPLEX,1,(0,180,255),2)
    ok,d=cv2.imencode(".jpg",img); return d.tobytes() if ok else b""
