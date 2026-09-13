# k1plak deployment

Requirements: Windows 10/11 or Linux, Python 3.10+, i5-9400F-class CPU,
8 GB RAM (16 GB recommended for 10+ cameras), and storage sized for retained
JPEGs (plan roughly 1–5 GB per camera/month depending on event rate).

```powershell
cd D:\plak01
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_models.py
python start_all.py
```

On Linux, use `python3 -m venv .venv`, activate with `source .venv/bin/activate`,
and adjust Windows paths in `config.yaml`. Add cameras through the web UI at
`http://server:5000/cameras`; set RTSP credentials, ROI as `x1,y1,x2,y2`, and
the camera speed threshold. View live streams at `/live/<camera_id>`, search
events at `/search`, and export with `/export.csv`.

For CPU tuning, prefer NCNN, reduce detector image size to 320, set
`frame_skip: 1` for busy multi-camera deployments, lower camera resolution,
and limit simultaneous workers to the available CPU cores. The launcher creates
one daemon thread per enabled camera; failed connections retry for 5, 10 and
20 seconds, then are logged offline until restart.
