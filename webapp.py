"""k1plak lightweight offline Flask UI."""
from __future__ import annotations
import csv, io, os, sqlite3, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, session, url_for, send_file, flash
from werkzeug.security import check_password_hash, generate_password_hash
from frame_buffer import get as get_frame, placeholder

BASE=Path(__file__).resolve().parent
DB_PATH=BASE/"k1plak.db"
app=Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key=os.environ.get("K1PLAK_SECRET","change-this-local-secret")
app.permanent_session_lifetime=timedelta(minutes=30)
LOCK=threading.RLock()
SCHEMA="""
CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, name TEXT UNIQUE, permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL, group_id INTEGER, must_change INTEGER DEFAULT 0, active INTEGER DEFAULT 1, FOREIGN KEY(group_id) REFERENCES groups(id));
CREATE TABLE IF NOT EXISTS cameras(id INTEGER PRIMARY KEY, name TEXT, ip TEXT, port INTEGER DEFAULT 554, username TEXT, password TEXT, zone TEXT, speed_threshold REAL DEFAULT 60, enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS detections(id INTEGER PRIMARY KEY, plate TEXT, category TEXT, speed REAL, camera_id INTEGER, timestamp TEXT, vehicle_image TEXT, plate_image TEXT, violation INTEGER DEFAULT 0, stopped_seconds REAL DEFAULT 0, FOREIGN KEY(camera_id) REFERENCES cameras(id));
CREATE TABLE IF NOT EXISTS system_logs(id INTEGER PRIMARY KEY, level TEXT, message TEXT, camera_id INTEGER, timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY, username TEXT, action TEXT, detail TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
DEFAULT_PERMS="view_live,view_logs,export_reports,manage_users,edit_cameras"
def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; c.executescript(SCHEMA)
    c.execute("INSERT OR IGNORE INTO groups(id,name,permissions) VALUES(1,'Admin',?)",(DEFAULT_PERMS,))
    c.execute("INSERT OR IGNORE INTO groups(name,permissions) VALUES('Operator','view_live,export_reports')")
    c.execute("INSERT OR IGNORE INTO groups(name,permissions) VALUES('Supervisor','view_logs,manage_users')")
    c.execute("INSERT OR IGNORE INTO users(username,password_hash,group_id,must_change) VALUES('admin',?,?,1)",
              (generate_password_hash("admin123"),1)); c.commit(); return c
def audit(action,detail=""):
    if session.get("user"): db().execute("INSERT INTO audit_logs(username,action,detail) VALUES(?,?,?)",(session["user"],action,detail)).connection.commit()
def perms():
    c=db(); r=c.execute("SELECT g.permissions FROM users u JOIN groups g ON g.id=u.group_id WHERE u.username=?",(session.get("user"),)).fetchone()
    return set((r["permissions"] if r else "").split(","))
def need(permission):
    if not session.get("user"): return redirect(url_for("login",next=request.path))
    if permission and permission not in perms() and "Admin" not in session.get("group",""): abort(403)
    return None
@app.before_request
def session_guard():
    if session.get("user"): session.permanent=True
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        r=db().execute("SELECT u.*,g.name group_name FROM users u JOIN groups g ON g.id=u.group_id WHERE username=? AND active=1",(request.form.get("username"),)).fetchone()
        if r and check_password_hash(r["password_hash"],request.form.get("password","")):
            session.update(user=r["username"],group=r["group_name"],must_change=bool(r["must_change"])); audit("login")
            return redirect(url_for("change_password") if r["must_change"] else url_for("dashboard"))
        flash("Username or password is incorrect","danger")
    return render_template("login.html")
@app.route("/logout")
def logout(): audit("logout"); session.clear(); return redirect(url_for("login"))
@app.route("/change-password",methods=["GET","POST"])
def change_password():
    if not session.get("user"): return redirect(url_for("login"))
    if request.method=="POST":
        p=request.form.get("password","")
        if len(p)<6: flash("Password must be at least 6 characters","danger")
        else:
            c=db(); c.execute("UPDATE users SET password_hash=?,must_change=0 WHERE username=?",(generate_password_hash(p),session["user"])); c.commit(); session["must_change"]=False; return redirect(url_for("dashboard"))
    return render_template("change_password.html")
@app.route("/")
def dashboard():
    x=need(None)
    if x:return x
    c=db(); today=datetime.now().strftime("%Y-%m-%d")
    stats={"cameras":c.execute("SELECT count(*) n FROM cameras").fetchone()["n"],"today":c.execute("SELECT count(*) n FROM detections WHERE timestamp LIKE ?",(today+"%",)).fetchone()["n"],"violations":c.execute("SELECT count(*) n FROM detections WHERE violation=1 AND timestamp LIKE ?",(today+"%",)).fetchone()["n"],"users":c.execute("SELECT count(*) n FROM users WHERE active=1").fetchone()["n"]}
    recent=c.execute("SELECT d.*,c.name camera FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id ORDER BY d.id DESC LIMIT 10").fetchall()
    return render_template("dashboard.html",stats=stats,recent=recent)

@app.route("/settings/storage", methods=["GET","POST"])
def storage_settings():
    x=need("edit_cameras")
    if x:return x
    c=db()
    if request.method=="POST":
        root=request.form.get("storage_root","D:/plak01/storage").strip()
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('storage_root',?)",(root,)); c.commit()
        flash("مسیر ذخیره‌سازی ذخیره شد","success")
    row=c.execute("SELECT value FROM settings WHERE key='storage_root'").fetchone()
    return render_template("storage_settings.html", storage_root=row["value"] if row else "D:/plak01/storage")
@app.route("/cameras",methods=["GET","POST"])
def cameras():
    x=need("edit_cameras")
    if x:return x
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO cameras(name,ip,port,username,password,zone,speed_threshold) VALUES(?,?,?,?,?,?,?)",(request.form["name"],request.form["ip"],request.form.get("port",554),request.form.get("username",""),request.form.get("password",""),request.form.get("zone",""),request.form.get("speed_threshold",60))); c.commit(); audit("camera_add",request.form["name"])
    return render_template("cameras.html",cameras=c.execute("SELECT * FROM cameras ORDER BY name").fetchall())
@app.route("/cameras/<int:cid>/toggle",methods=["POST"])
def camera_toggle(cid):
    x=need("edit_cameras")
    if x:return x
    c=db(); c.execute("UPDATE cameras SET enabled=1-enabled WHERE id=?",(cid,)); c.commit(); audit("camera_toggle",str(cid)); return redirect(url_for("cameras"))
@app.route("/cameras/<int:cid>/roi", methods=["GET","POST"])
def camera_roi(cid):
    x=need("edit_cameras")
    if x:return x
    c=db(); cam=c.execute("SELECT * FROM cameras WHERE id=?",(cid,)).fetchone()
    if not cam: abort(404)
    if request.method=="POST":
        import json
        try:
            data=request.get_json(silent=True) or {}
            points=data.get("points",[])
            if len(points)<4: return jsonify({"ok":False,"error":"حداقل ۴ نقطه لازم است"}),400
            points=[[int(p[0]),int(p[1])] for p in points]
            c.execute("UPDATE cameras SET zone=? WHERE id=?",(json.dumps({"points":points},ensure_ascii=False),cid)); c.commit(); audit("camera_roi",str(cid))
            return jsonify({"ok":True,"points":points})
        except Exception:return jsonify({"ok":False,"error":"مختصات نامعتبر است"}),400
    return render_template("roi_editor.html",camera=cam)
@app.route("/users",methods=["GET","POST"])
def users():
    x=need("manage_users")
    if x:return x
    c=db()
    if request.method=="POST":
        group=c.execute("SELECT id FROM groups WHERE name=?",(request.form.get("group","Operator"),)).fetchone()
        if group and request.form.get("username") and request.form.get("password"):
            c.execute("INSERT OR REPLACE INTO users(username,password_hash,group_id,must_change) VALUES(?,?,?,1)",
                      (request.form["username"],generate_password_hash(request.form["password"]),group["id"])); c.commit(); audit("user_upsert",request.form["username"])
    return render_template("users.html",users=c.execute("SELECT u.username,u.active,g.name group_name FROM users u JOIN groups g ON g.id=u.group_id ORDER BY u.username").fetchall(),groups=c.execute("SELECT name FROM groups").fetchall())
@app.route("/search")
def search():
    x=need(None)
    if x:return x
    q="SELECT d.*,c.name camera FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id WHERE 1=1"; args=[]
    if request.args.get("plate"): q+=" AND d.plate LIKE ?"; args.append("%"+request.args["plate"]+"%")
    if request.args.get("camera"): q+=" AND c.name=?"; args.append(request.args["camera"])
    if request.args.get("violation") in ("0","1"): q+=" AND d.violation=?"; args.append(request.args["violation"])
    q+=" ORDER BY d.timestamp DESC LIMIT 200"; return render_template("search.html",rows=db().execute(q,args).fetchall())
@app.route("/record/<int:did>")
def record(did):
    x=need(None)
    if x:return x
    r=db().execute("SELECT d.*,c.name camera FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id WHERE d.id=?",(did,)).fetchone()
    if not r: abort(404)
    return render_template("record.html",r=r)

@app.route("/media")
def media_query():
    x=need(None)
    if x:return x
    path=request.args.get("path","")
    p=Path(path)
    if not p.is_absolute(): p=BASE/p
    try: p.resolve().relative_to(BASE.resolve())
    except Exception: abort(403)
    if not p.exists() or not p.is_file(): abort(404)
    return send_file(p)
@app.route("/api/stats")
def api_stats():
    x=need(None)
    if x:return x
    c=db(); return jsonify({"detections_per_hour":[{"hour":h,"count":n} for h,n in c.execute("SELECT substr(timestamp,12,2) hour,count(*) n FROM detections WHERE timestamp>=datetime('now','-1 day') GROUP BY hour")],"violations_by_camera":[{"camera":n,"count":v} for n,v in c.execute("SELECT coalesce(c.name,'unknown'),count(*) FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id WHERE violation=1 AND timestamp>=datetime('now','-7 day') GROUP BY c.name")]})
@app.route("/api/stats/hourly")
def stats_hourly():
    x=need(None)
    if x:return x
    rows=db().execute("SELECT substr(timestamp,1,13) hour,count(*) n FROM detections WHERE timestamp>=datetime('now','-1 day') GROUP BY hour ORDER BY hour").fetchall()
    return jsonify({"labels":[r["hour"] for r in rows],"values":[r["n"] for r in rows]})
@app.route("/api/stats/violations_by_camera")
def stats_violations():
    x=need(None)
    if x:return x
    rows=db().execute("SELECT coalesce(c.name,'unknown') camera,count(*) n FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id WHERE violation=1 AND timestamp>=datetime('now','-7 day') GROUP BY camera").fetchall()
    return jsonify({"labels":[r["camera"] for r in rows],"values":[r["n"] for r in rows]})
@app.route("/api/stats/vehicle_types")
def stats_types():
    x=need(None)
    if x:return x
    rows=db().execute("SELECT category,count(*) n FROM detections WHERE timestamp LIKE ? GROUP BY category",(datetime.now().strftime("%Y-%m-%d")+"%",)).fetchall()
    return jsonify({"labels":[r["category"] for r in rows],"values":[r["n"] for r in rows]})
@app.route("/api/cameras")
def api_cameras():
    x=need("view_live")
    if x:return x
    return jsonify([dict(r) for r in db().execute("SELECT id,name,ip,enabled FROM cameras").fetchall()])
@app.route("/export.csv")
def export_csv():
    x=need("export_reports")
    if x:return x
    out=io.StringIO(); w=csv.writer(out); w.writerow(["plate","category","speed","camera","timestamp","violation"])
    for r in db().execute("SELECT d.plate,d.category,d.speed,c.name,d.timestamp,d.violation FROM detections d LEFT JOIN cameras c ON c.id=d.camera_id ORDER BY d.timestamp DESC"): w.writerow(list(r))
    audit("report_export"); return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=detections.csv"})
@app.route("/live/<int:camera_id>")
def live(camera_id):
    x=need("view_live")
    if x:return x
    return render_template("live.html",camera_id=camera_id)
@app.route("/api/live/stream/<int:camera_id>")
def stream(camera_id):
    x=need("view_live")
    if x:return x
    def gen():
        while True:
            row=get_frame(camera_id)
            data=row[0] if row else placeholder(f"camera {camera_id}")
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "+str(len(data)).encode()+b"\r\n\r\n"+data+b"\r\n"
            time.sleep(.1)
    return Response(gen(),mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/live/snapshot/<int:camera_id>")
def snapshot(camera_id):
    x=need("view_live")
    if x:return x
    row=get_frame(camera_id)
    data=row[0] if row else placeholder(f"camera {camera_id}")
    return Response(data,mimetype="image/jpeg")

@app.route("/video_feed")
def video_feed():
    """Compatibility endpoint: /video_feed?camera_id=1 or /video_feed/<id>."""
    cid=request.args.get("camera_id", "0")
    try: cid=int(cid)
    except ValueError: cid=0
    x=need("view_live")
    if x:return x
    def gen():
        while True:
            row=get_frame(cid)
            data=row[0] if row else placeholder(f"camera {cid}")
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "+str(len(data)).encode()+b"\r\n\r\n"+data+b"\r\n"
            time.sleep(.1)
    return Response(gen(),mimetype="multipart/x-mixed-replace; boundary=frame")
if __name__=="__main__": db(); app.run(host="0.0.0.0",port=5000,threaded=True)
