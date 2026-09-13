from dataclasses import dataclass, field
from typing import Dict, List
import math

def iou(a,b):
    ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
    ix1,iy1=max(ax1,bx1),max(ay1,by1); ix2,iy2=min(ax2,bx2),min(ay2,by2)
    inter=max(0,ix2-ix1)*max(0,iy2-iy1)
    area=lambda q:max(0,q[2]-q[0])*max(0,q[3]-q[1])
    den=area(a)+area(b)-inter
    return inter/den if den else 0.0

@dataclass
class Track:
    track_id: int
    bbox: tuple
    first_seen: float
    last_seen: float
    centers: List[tuple] = field(default_factory=list)
    missed: int = 0

class IOUTracker:
    def __init__(self, threshold=.25, max_missed=15):
        self.threshold, self.max_missed, self.next_id = threshold, max_missed, 1
        self.tracks: Dict[int,Track] = {}
    def update(self, detections, timestamp):
        unmatched=set(range(len(detections)))
        for t in list(self.tracks.values()):
            best = max(unmatched, key=lambda i:iou(t.bbox,detections[i].bbox), default=None)
            if best is not None and iou(t.bbox,detections[best].bbox)>=self.threshold:
                t.bbox=detections[best].bbox; t.last_seen=timestamp; t.missed=0
                b=t.bbox; t.centers.append(((b[0]+b[2])/2,(b[1]+b[3])/2)); unmatched.remove(best)
            else: t.missed += 1
        for tid in [k for k,v in self.tracks.items() if v.missed>self.max_missed]: del self.tracks[tid]
        for i in unmatched:
            b=detections[i].bbox; c=((b[0]+b[2])/2,(b[1]+b[3])/2)
            self.tracks[self.next_id]=Track(self.next_id,b,timestamp,timestamp,[c]); self.next_id+=1
        return list(self.tracks.values())
