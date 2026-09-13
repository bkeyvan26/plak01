from pathlib import Path
from datetime import datetime
import cv2

class Storage:
    def __init__(self, root, jpeg_quality=90, plate_upscale=4, plate_min_width=640):
        self.root=Path(root); self.jpeg_quality=jpeg_quality
        self.plate_upscale=plate_upscale; self.plate_min_width=plate_min_width
    def save(self, camera, plate, frame, plate_crop, metadata, when=None, camera_id=None):
        when=when or datetime.now(); day=when.strftime("%Y-%m-%d"); stamp=when.strftime("%H%M%S")
        # Keep filenames portable across Windows/network shares; OCR mojibake
        # and control characters must never become path components.
        safe="".join(c if (c.isascii() and (c.isalnum() or c in "_-")) or
                     ("\u0600" <= c <= "\u06ff") else "_" for c in (plate or "unknown"))
        safe=safe.strip(" .") or "unknown"
        folder=self.root/camera/day; folder.mkdir(parents=True,exist_ok=True)
        suffix=f"_{camera_id}" if camera_id is not None else ""
        base=folder/f"{safe}_{stamp}{suffix}"; image=frame.copy()
        cv2.putText(image, f"{plate} {metadata.get('speed_kmh',0):.1f}km/h {stamp}",
                    (10,30), cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,0),2)
        cv2.imwrite(str(base.with_suffix(".jpg")),image,[cv2.IMWRITE_JPEG_QUALITY,max(95,self.jpeg_quality)])
        # Plate boxes are often only a few dozen pixels high. Preserve the
        # original crop, then enlarge with Lanczos and mild unsharp masking so
        # OCR/debug images remain useful without inventing characters.
        crop_img = plate_crop
        if crop_img is None or getattr(crop_img, "size", 0) == 0:
            crop_img = frame
        h,w=crop_img.shape[:2]
        target_w=max(self.plate_min_width,int(w*self.plate_upscale))
        target_h=max(160,int(h*target_w/max(w,1)))
        up=cv2.resize(crop_img,(target_w,target_h),interpolation=cv2.INTER_LANCZOS4)
        blur=cv2.GaussianBlur(up,(0,0),1.0)
        up=cv2.addWeighted(up,1.35,blur,-0.35,0)
        plate_path=folder/f"{safe}_{stamp}{suffix}_plate.jpg"
        cv2.imwrite(str(plate_path),up,[cv2.IMWRITE_JPEG_QUALITY,98])
        base.with_suffix(".txt").write_text("\n".join(f"{k}={v}" for k,v in metadata.items()),encoding="utf-8")
        return {"vehicle": str(base.with_suffix(".jpg")), "plate": str(plate_path), "meta": str(base.with_suffix(".txt"))}
