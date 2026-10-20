from flask import Flask, redirect, render_template, request, session, jsonify, url_for,flash
from functools import wraps
from firebase_admin import credentials, firestore, auth as firebase_auth
import firebase_admin
from datetime import timedelta
import os
from dotenv import load_dotenv
from firebase_admin import storage
import requests
from flask import Response,stream_with_context
from datetime import datetime

load_dotenv()


if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-auth.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': '***' 
    })



ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-auth.json")
    firebase_admin.initialize_app(cred)

db = firestore.client() 
bucket = storage.bucket()



def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session["user"].get("role") != "admin":
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper



@app.route("/auth", methods=["POST"])
def auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing token"}), 401

    try:
        token = auth_header.split("Bearer ")[1]
        decoded = firebase_auth.verify_id_token(token, clock_skew_seconds=10)
        uid = decoded.get("uid")
        email = decoded.get("email")

        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            role = "admin" if email == ADMIN_EMAIL else "user"
            user_data = {
                "email": email,
                "role": role,
                "rfid_tag": "",  
                "created_at": firestore.SERVER_TIMESTAMP
            }
            user_ref.set(user_data)
        else:
            role = user_doc.to_dict().get("role", "user")

        session["user"] = {
            "uid": uid,
            "email": email,
            "role": role 
        }

        if role == "admin":
            return jsonify({"redirect": url_for("dashboard")})
        return jsonify({"redirect": url_for("home")})

    except Exception as e:
        print(f"Auth Error: {e}")
        return jsonify({"error": str(e)}), 401



@app.route("/")
def present():
    return render_template("index1.html")

@app.route("/next")
def landing():
    return render_template("home.html")

@app.route("/login")
def login():
    if "user" in session:
        is_admin = session["user"].get("role") == "admin"
        return redirect(url_for("dashboard") if is_admin else url_for("home"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



@app.route("/dashboard")
@admin_required
def dashboard():
    users_ref = db.collection("users")
    docs = users_ref.stream()
    
    users_list = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        data['first_name'] = data.get('first_name', 'Nume')
        data['last_name'] = data.get('last_name', 'Necunoscut')
        users_list.append(data)
    
    return render_template("dashboard.html", users=users_list)


@app.route("/user_details/<user_id>")
@admin_required
def user_details(user_id):
    user_doc = db.collection("users").document(user_id).get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        user_data['id'] = user_doc.id
        user_data['phone'] = user_data.get('phone', 'Nespecificat')
        user_data['address'] = user_data.get('address', 'Nespecificat')
        user_data['company'] = user_data.get('company', 'Nespecificat')
        user_data['password'] = user_data.get('password', '********')
        user_data['allowed_rooms'] = user_data.get('allowed_rooms', [])
        
        if 'face_image_url' not in user_data or not user_data['face_image_url']:
            user_data['face_image_url'] = "/static/images/default-avatar.png"
            
        return render_template("user_details.html", user=user_data)
    return "Utilizator negăsit", 404

@app.route("/update_user_info", methods=["POST"])
@admin_required
def update_user_info():
    data = request.json
    user_id = data.get("userId")
    
    updated_fields = {
        "phone": data.get("phone"),
        "address": data.get("address"),
        "company": data.get("company"),
        "password": data.get("password"),
        "rfid_tag": data.get("rfid_tag"),
        "allowed_rooms": [room.strip() for room in data.get("rooms", "").split(",") if room.strip()]
    }
    
    try:
        db.collection("users").document(user_id).update(updated_fields)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Update Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/upload_face/<user_id>", methods=["POST"])
@admin_required
def upload_face(user_id):
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Fișier lipsă"}), 400
    
    file = request.files['file']
    try:
        blob = bucket.blob(f"faces/{user_id}.jpg")
        blob.upload_from_string(
            file.read(),
            content_type=file.content_type
        )
        blob.make_public()
        image_url = blob.public_url
        db.collection("users").document(user_id).update({
            "face_image_url": image_url
        })
        
        return jsonify({"success": True, "url": image_url})
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    


@app.route("/home")
@login_required
def home():
    return render_template("home.html")

@app.route('/video_proxy')
@admin_required
def video_proxy():
    url = "http://10.113.21.136:8080/video_feed"
    r = requests.get(url, stream=True, timeout=10)
    tip_continut = r.headers.get('content-type','multipart/x-mixed-replace; boundary=frame')
    return Response(stream_with_context(r.iter_content(chunk_size=1024)),content_type=tip_continut)

@app.route("/livecam")
@admin_required
def livecam():
    return render_template("livecam.html")

@app.route('/lcd_proxy')
@admin_required
def lcd_proxy():
    url = "http://10.113.21.136:8080/lcd_status"
    
    try:
        import requests
        r = requests.get(url, timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"line1": "Sistem Offline", "line2": "Verificati camera"})

@app.route('/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        company = request.form.get('company')
        password = request.form.get('password')
        rfid_tag = request.form.get('rfid_tag', '')
        
        rooms_input = request.form.get('allowed_rooms', '')
        
        allowed_rooms = [room.strip() for room in rooms_input.split(',')] if rooms_input else []

        now = datetime.now()
        
        created_at = now.strftime("%B %d, %Y at %I:%M:%S %p")

        
        new_user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "address": address,
            "company": company,
            "password": password,
            "rfid_tag": rfid_tag,
            "allowed_rooms": allowed_rooms,
            "role": "user",             
            "created_at": created_at,   
            "face_image_url": ""        
        }

        try:
            db.collection('users').add(new_user_data)
            flash('Utilizator adăugat cu succes!', 'success')
            return redirect(url_for('dashboard')) 
            
        except Exception as e:
            print(f"Eroare la adăugarea utilizatorului: {e}")
            flash('A apărut o eroare la salvarea în baza de date.', 'danger')

    
    return render_template('add_user.html')


@app.route('/audit_logs')
@admin_required
def audit_logs():
    logs_ref = db.collection('access_logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100).stream()
    
    istoric_loguri = []
    for doc in logs_ref:
        date = doc.to_dict()
        
        if date.get('timestamp'):
            timp = date['timestamp']
            date['data_formatata'] = timp.strftime("%d %b %Y")
            date['ora_formatata'] = timp.strftime("%H:%M:%S")
        else:
            date['data_formatata'] = "N/A"
            date['ora_formatata'] = "N/A"
            
        istoric_loguri.append(date)

    return render_template('audit_logs.html', logs=istoric_loguri)



@app.route("/terms")
def terms(): return render_template("terms.html")

@app.route("/privacy")
def privacy(): return render_template("privacy.html")

@app.route("/signup")
def signup(): return render_template("signup.html")

@app.route("/reset-password")
def reset_password(): return render_template("forgot_password.html")

if __name__ == "__main__":
    app.run(debug=True)
