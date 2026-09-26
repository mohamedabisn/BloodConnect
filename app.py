from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, re

app=Flask(__name__)
app.secret_key="bloodconnect-local-demo-key"
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

DB = os.path.join(DATA_DIR, "bloodconnect.db")

def db():
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; return con

def init():
    con=db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,blood_group TEXT,district TEXT,area TEXT,phone TEXT,available INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,blood_group TEXT,units INTEGER,district TEXT,area TEXT,hospital TEXT,urgency TEXT,details TEXT,status TEXT DEFAULT 'OPEN',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS hospitals(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,district TEXT,area TEXT,phone TEXT,blood_note TEXT,latitude REAL,longitude REAL);
    CREATE TABLE IF NOT EXISTS camps(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,venue TEXT,district TEXT,date TEXT,time TEXT,organizer TEXT);
    ''')
    if con.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]==0:
        con.executemany("INSERT INTO hospitals(name,district,area,phone,blood_note,latitude,longitude) VALUES(?,?,?,?,?,?,?)",[
        ("Kauvery Hospital","Tiruchirappalli","Tennur","0431-4077777","Call hospital blood bank for current stock",10.8265,78.6867),
        ("Apollo Speciality Hospitals","Tiruchirappalli","Ariyamangalam","0431-3088999","Blood bank information subject to confirmation",10.7987,78.7140),
        ("MGM Government Hospital","Tiruchirappalli","Puthur","0431-2771000","Government hospital — verify current availability",10.8162,78.6837),
        ("SRM Medical College Hospital","Tiruchirappalli","Irungalur","0431-3086000","Contact blood bank before travel",10.9025,78.7320)])
    if con.execute("SELECT COUNT(*) FROM camps").fetchone()[0]==0:
        con.executemany("INSERT INTO camps(name,venue,district,date,time,organizer) VALUES(?,?,?,?,?,?)",[
        ("Campus Blood Donation Camp","Bishop Heber College","Tiruchirappalli","2026-09-05","09:00 - 14:00","Student Volunteer Cell"),
        ("Community Blood Drive","National College","Tiruchirappalli","2026-09-12","09:00 - 15:00","NSS Unit"),
        ("Youth Blood Donation Camp","Jamals Mohamed College","Tiruchirappalli","2026-09-20","10:00 - 15:00","NSS / YRC")])
    con.commit(); con.close()

@app.context_processor
def common():
    return {"logged":"uid" in session,"user_name":session.get("name","")}

@app.route("/")
def home():
    con=db()
    donors=con.execute("SELECT COUNT(*) c FROM users WHERE available=1").fetchone()["c"]
    requests=con.execute("SELECT COUNT(*) c FROM requests WHERE status='OPEN'").fetchone()["c"]
    hospitals=con.execute("SELECT COUNT(*) c FROM hospitals").fetchone()["c"]
    camps=con.execute("SELECT * FROM camps ORDER BY date LIMIT 3").fetchall()
    con.close()
    return render_template("home.html",donors=donors,requests=requests,hospitals=hospitals,camps=camps)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        f=request.form
        try:
            con=db(); con.execute("INSERT INTO users(name,email,password,blood_group,district,area,phone,available) VALUES(?,?,?,?,?,?,?,?)",
            (f["name"],f["email"].lower(),generate_password_hash(f["password"]),f["blood_group"],f["district"],f["area"],f["phone"],1))
            con.commit(); con.close(); flash("Donor account created successfully.","ok"); return redirect(url_for("login"))
        except sqlite3.IntegrityError: flash("Email already registered.","error")
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        con=db(); u=con.execute("SELECT * FROM users WHERE email=?",(request.form["email"].lower(),)).fetchone(); con.close()
        if u and check_password_hash(u["password"],request.form["password"]):
            session["uid"]=u["id"]; session["name"]=u["name"]; return redirect(url_for("dashboard"))
        flash("Invalid email or password.","error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    con=db()
    donors=con.execute("SELECT * FROM users WHERE available=1 ORDER BY id DESC LIMIT 8").fetchall()
    reqs=con.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 6").fetchall()
    hospitals=con.execute("SELECT * FROM hospitals").fetchall()
    camps=con.execute("SELECT * FROM camps ORDER BY date LIMIT 4").fetchall()
    con.close()
    return render_template("dashboard.html",donors=donors,reqs=reqs,hospitals=hospitals,camps=camps)

@app.route("/donors")
def donors():
    bg=request.args.get("blood_group",""); district=request.args.get("district",""); area=request.args.get("area","")
    q="SELECT * FROM users WHERE available=1"; vals=[]
    if bg:q+=" AND blood_group=?";vals.append(bg)
    if district:q+=" AND district=?";vals.append(district)
    if area:q+=" AND area LIKE ?";vals.append("%"+area+"%")
    con=db(); rows=con.execute(q+" ORDER BY id DESC",vals).fetchall();con.close()
    return render_template("donors.html",rows=rows,bg=bg,district=district,area=area)

@app.route("/request",methods=["GET","POST"])
def blood_request():
    if "uid" not in session:return redirect(url_for("login"))
    if request.method=="POST":
        f=request.form; details=f.get("details","")
        urgency="URGENT" if any(x in details.lower() for x in ["emergency","urgent","critical","accident","operation today"]) else "NORMAL"
        con=db();con.execute("INSERT INTO requests(user_id,blood_group,units,district,area,hospital,urgency,details) VALUES(?,?,?,?,?,?,?,?)",
        (session["uid"],f["blood_group"],f["units"],f["district"],f["area"],f["hospital"],urgency,details));con.commit();con.close()
        flash("Blood request posted. Matching donors can now see it.","ok");return redirect(url_for("dashboard"))
    return render_template("request.html")

@app.route("/hospitals")
def hospitals():
    con=db(); rows=con.execute("SELECT * FROM hospitals").fetchall();con.close()
    return render_template("hospitals.html",rows=rows)

@app.route("/camps")
def camps():
    con=db(); rows=con.execute("SELECT * FROM camps ORDER BY date").fetchall();con.close()
    return render_template("camps.html",rows=rows)

@app.route("/api/donor/<int:id>")
def donor_api(id):
    con=db();u=con.execute("SELECT name,blood_group,district,area,phone FROM users WHERE id=? AND available=1",(id,)).fetchone();con.close()
    return jsonify(dict(u) if u else {"error":"Not available"})

init()
app.run(debug=True,host="127.0.0.1",port=5000)
