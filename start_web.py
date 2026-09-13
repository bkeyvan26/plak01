from webapp import app, db
if __name__=="__main__":
    db(); app.run(host="0.0.0.0",port=5000,threaded=True)
