"""Probe the test RTSP camera and optionally save/display a frame."""
import argparse, time
from pathlib import Path
import cv2

URLS=[
    "rtsp://root:123456@172.20.34.112:554/axis-media/media.amp",
    "rtsp://root:123456@172.20.34.112:554/axis-media/media.a",
    "rtsp://root:123456@172.20.34.112:554/Streaming/Channels/101",
    "rtsp://root:123456@172.20.34.112:554/",
]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seconds",type=int,default=5); ap.add_argument("--save",default="storage/rtsp_probe.jpg"); ap.add_argument("--show",action="store_true")
    a=ap.parse_args()
    for url in URLS:
        print("Testing RTSP:",url)
        cap=cv2.VideoCapture(url,cv2.CAP_FFMPEG)
        if not cap.isOpened(): cap.release(); continue
        start=time.time(); frames=0; sample=None
        while time.time()-start<a.seconds:
            ok,frame=cap.read()
            if ok: frames+=1; sample=frame
        cap.release()
        if sample is not None:
            p=Path(a.save); p.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(p),sample)
            print(f"SUCCESS: {frames} frames, approx FPS {frames/max(a.seconds,1):.1f}, sample: {p.resolve()}")
            if a.show: cv2.imshow("RTSP",sample); cv2.waitKey(0); cv2.destroyAllWindows()
            return
        print("Connection opened but no frames were received.")
    raise SystemExit("No RTSP URL produced frames; check path, codec, credentials, and network access.")
if __name__=="__main__": main()
