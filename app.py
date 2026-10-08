import os
import sqlite3
import random
import base64
import secrets
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash

from python_files.personal_info_data import (
    GENDER_LIST, ACTIVITY_LEVEL_LIST, DIET_TYPE_LIST, GOAL_TYPE_LIST, WORKOUT_STYLE_LIST
)
from python_files.meal_data import MEAL_TEXT_KEYWORDS, get_food_nutrition, get_goal_note
from python_files.packed_food_data import RISKY_INGREDIENT_LIST
from python_files.ocr_helper import read_text_from_image
from python_files.compare_logic import compare_products
from python_files.smart_scan_helper import (
    analyze_meal_photo, analyze_meal_text, analyze_packed_food,
    analyze_packed_food_text, compare_products_smart, chat_with_gemini, synthesize_speech, transcribe_audio,
    translate_text, SmartScanUnavailableError
)
from python_files.fitness_data import (
    calculate_bmi, calculate_calorie_need, calculate_water_intake, calculate_step_goal
)
from python_files.allergy_data import COMMON_ALLERGENS
from python_files.external_food_data import verify_nutrition, enrich_packed_result

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
DATABASE_FOLDER = os.path.join(BASE_DIR, "database_files")
DATABASE_PATH = os.path.join(DATABASE_FOLDER, "database.db")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATABASE_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_names(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    conn = get_db_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        security_question TEXT NOT NULL DEFAULT 'What is your favorite food?',
        security_answer TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS scan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        food_name TEXT NOT NULL,
        image_path TEXT DEFAULT '',
        date_added TEXT NOT NULL,
        category TEXT DEFAULT 'meal',
        calories REAL DEFAULT 0,
        water_liters REAL DEFAULT 0,
        safety_status TEXT DEFAULT '',
        source TEXT DEFAULT 'gemini'
    );
    CREATE TABLE IF NOT EXISTS personal_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        age TEXT, gender TEXT, weight TEXT, height TEXT, activity_level TEXT,
        diet_type TEXT, allergies TEXT, medical_report_path TEXT,
        goal_type TEXT, target_weight TEXT, workout_style TEXT,
        daily_steps_goal TEXT, is_filled INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS diary_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        note_text TEXT NOT NULL,
        mood TEXT,
        date_added TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS water_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        liters REAL NOT NULL,
        date_added TEXT NOT NULL
    );
    """)
    # Safe migrations for databases created by the 75% version.
    existing = _column_names(conn, "scan_history")
    for name, definition in {
        "calories": "REAL DEFAULT 0",
        "water_liters": "REAL DEFAULT 0",
        "safety_status": "TEXT DEFAULT ''",
        "source": "TEXT DEFAULT 'gemini'",
    }.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE scan_history ADD COLUMN {name} {definition}")
    conn.commit()
    conn.close()


init_db()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def get_personal_info(username):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM personal_info WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_uploaded_file(file_storage, prefix):
    filename = (file_storage.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = "jpg"
    file_name = f"{prefix}_{secrets.token_hex(8)}.{ext}"
    saved_path = os.path.join(UPLOAD_FOLDER, file_name)
    file_storage.save(saved_path)
    return saved_path


def save_camera_capture(camera_string, prefix):
    try:
        _, encoded_bytes = camera_string.split(",", 1)
        raw = base64.b64decode(encoded_bytes, validate=True)
    except Exception as exc:
        raise ValueError("Invalid camera capture") from exc
    if not raw:
        raise ValueError("Empty camera capture")
    file_name = f"{prefix}_{secrets.token_hex(8)}.jpg"
    saved_path = os.path.join(UPLOAD_FOLDER, file_name)
    with open(saved_path, "wb") as fh:
        fh.write(raw)
    return saved_path


def public_path(path):
    if not path:
        return ""
    rel = os.path.relpath(path, BASE_DIR).replace(os.sep, "/")
    return "/" + rel


def safe_allergies(info):
    if not info or not info.get("allergies"):
        return []
    return [x.strip().lower() for x in str(info["allergies"]).split(",") if x.strip()]


def allergy_matches(info, text, extra_terms=None):
    allergies = safe_allergies(info)
    haystack = " ".join([str(text or "")] + [str(x) for x in (extra_terms or [])]).lower()
    matches = []
    aliases = {
        "dairy": ["milk", "cheese", "cream", "whey", "casein", "yogurt", "lactose"],
        "milk": ["milk", "whey", "casein", "lactose", "cream", "cheese"],
        "peanut": ["peanut", "groundnut", "arachis"],
        "nuts": ["almond", "cashew", "walnut", "pistachio", "hazelnut", "nut"],
        "shellfish": ["prawn", "shrimp", "crab", "lobster", "shellfish"],
        "gluten": ["wheat", "barley", "rye", "gluten"],
        "wheat": ["wheat", "atta", "maida", "flour"],
        "soy": ["soy", "soya", "tofu"],
        "egg": ["egg", "albumin", "mayonnaise"],
    }
    for allergy in allergies:
        terms = [allergy] + aliases.get(allergy, [])
        if any(term in haystack for term in terms):
            matches.append(allergy)
    return sorted(set(matches))


def safety_class(value):
    s = str(value or "").lower()
    if any(x in s for x in ["not safe", "not recommended", "unsafe", "limit", "high", "risk", "warning"]):
        return "danger"
    if any(x in s for x in ["moderation", "moderate", "watch"]):
        return "warning"
    return "safe"


def record_scan(username, name, image_path="", category="meal", calories=0, safety_status="", source="gemini"):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO scan_history
           (username, food_name, image_path, date_added, category, calories, safety_status, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (username, name, image_path, datetime.now().strftime("%Y-%m-%d %H:%M"),
         category, float(calories or 0), safety_status, source)
    )
    conn.commit()
    conn.close()



LANGUAGE_LABELS = {"English": "English", "Hindi": "Hindi"}
HEALTH_TIPS = {
    "English": [
        "Add a serving of vegetables or fruit to your main meal.",
        "Choose a protein source at each main meal when practical.",
        "Check both serving size and added sugar when reading a packaged-food label.",
        "Regular movement, adequate sleep and hydration support everyday health.",
        "A healthy food can still be high in calories, so portion size matters.",
        "Prefer minimally processed foods more often and vary your food choices."
    ],
    "Hindi": [
        "अपने मुख्य भोजन में सब्जियों या फलों की एक मात्रा जरूर शामिल करें।",
        "जहाँ संभव हो, हर मुख्य भोजन में प्रोटीन का एक अच्छा स्रोत लें।",
        "पैकेज्ड फूड का लेबल पढ़ते समय सर्विंग साइज और अतिरिक्त चीनी दोनों देखें।",
        "नियमित गतिविधि, पर्याप्त नींद और पानी रोज़मर्रा की सेहत के लिए महत्वपूर्ण हैं।",
        "कोई भोजन पौष्टिक होने के बावजूद कैलोरी में अधिक हो सकता है, इसलिए मात्रा महत्वपूर्ण है।",
        "कम प्रोसेस किए गए भोजन को अधिक बार चुनें और अपने भोजन में विविधता रखें।"
    ]
}
def current_language():
    return session.get("language", "English") if "username" in session else "English"

def set_language(language):
    return "Hindi" if str(language).lower() == "hindi" else "English"

@app.context_processor
def inject_ui_state():
    return {"current_language": current_language(), "language_label": "Hindi" if current_language()=="English" else "English"}

def localized_text(english, hindi):
    return hindi if current_language() == "Hindi" else english

def random_health_tip():
    return random.choice(HEALTH_TIPS[current_language()])


@app.post("/api/language")
def api_language():
    payload = request.get_json(silent=True) or {}
    language = set_language(payload.get("language", "English"))
    session["language"] = language
    return jsonify({"ok": True, "language": language})

# ---------------- AUTH ----------------
@app.route("/")
def home():
    return redirect(url_for("dashboard" if "username" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        valid = False
        if user:
            stored = user["password"]
            if str(stored).startswith(("pbkdf2:", "scrypt:")):
                valid = check_password_hash(stored, password)
            else:
                valid = secrets.compare_digest(str(stored), password)
        if valid:
            session["username"] = username
            session.setdefault("language", "English")
            return redirect(url_for("dashboard"))
        flash(localized_text("Incorrect username or password.", "उपयोगकर्ता नाम या पासवर्ड सही नहीं है।"), "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        question = request.form.get("security_question", "What is your favorite food?")
        answer = request.form.get("security_answer", "").strip().lower()
        if len(username) < 3 or len(password) < 4:
            flash("Username kam se kam 3 aur password 4 characters ka rakho.", "error")
            return render_template("register.html")
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password, security_question, security_answer) VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password), question, answer)
            )
            conn.execute("INSERT OR IGNORE INTO personal_info (username, is_filled) VALUES (?, 0)", (username,))
            conn.commit()
            session["username"] = username
            session.setdefault("language", "English")
            flash(localized_text("Account created successfully.", "खाता सफलतापूर्वक बना दिया गया है।"), "success")
            return redirect(url_for("personal_info"))
        except sqlite3.IntegrityError:
            flash(localized_text("That username is already in use.", "यह उपयोगकर्ता नाम पहले से उपयोग में है।"), "error")
        finally:
            conn.close()
    return render_template("register.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        question = request.form.get("security_question", "")
        answer = request.form.get("security_answer", "").strip().lower()
        new_password = request.form.get("new_password", "")
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND security_question = ? AND security_answer = ?",
            (username, question, answer)
        ).fetchone()
        if user and len(new_password) >= 4:
            conn.execute("UPDATE users SET password = ? WHERE username = ?",
                         (generate_password_hash(new_password), username))
            conn.commit()
            conn.close()
            flash(localized_text("Password updated. You can sign in now.", "पासवर्ड अपडेट हो गया है। अब साइन इन करें।"), "success")
            return redirect(url_for("login"))
        conn.close()
        flash(localized_text("The details did not match, or the password is too short.", "जानकारी मेल नहीं खाती या पासवर्ड बहुत छोटा है।"), "error")
    return render_template("forgot_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- PROFILE ----------------
@app.route("/personal-info", methods=["GET", "POST"])
@login_required
def personal_info():
    active_user = session["username"]
    if request.method == "POST":
        conn = get_db_connection()
        medical_path = None
        med_file = request.files.get("medical_report")
        if med_file and med_file.filename:
            medical_path = public_path(save_uploaded_file(med_file, "medical"))
        old = conn.execute("SELECT medical_report_path FROM personal_info WHERE username = ?", (active_user,)).fetchone()
        if not medical_path and old:
            medical_path = old["medical_report_path"] or ""
        conn.execute("""
            UPDATE personal_info SET age=?, gender=?, weight=?, height=?, activity_level=?,
            diet_type=?, allergies=?, medical_report_path=?, goal_type=?, target_weight=?,
            workout_style=?, daily_steps_goal=?, is_filled=1 WHERE username=?
        """, (
            request.form.get("age", "").strip(), request.form.get("gender", ""),
            request.form.get("weight", "").strip(), request.form.get("height", "").strip(),
            request.form.get("activity_level", ""), request.form.get("diet_type", ""),
            request.form.get("allergies", "").strip(), medical_path or "",
            request.form.get("goal_type", ""), request.form.get("target_weight", "").strip(),
            request.form.get("workout_style", ""), request.form.get("daily_steps_goal", "").strip(),
            active_user
        ))
        conn.commit()
        conn.close()
        flash(localized_text("Profile updated successfully.", "प्रोफाइल सफलतापूर्वक अपडेट हो गई है।"), "success")
        return redirect(url_for("dashboard"))
    return render_template(
        "personal_info.html", info=get_personal_info(active_user),
        gender_list=GENDER_LIST, activity_list=ACTIVITY_LEVEL_LIST,
        diet_list=DIET_TYPE_LIST, goal_list=GOAL_TYPE_LIST, workout_list=WORKOUT_STYLE_LIST
    )


@app.route("/skip-personal-info")
@login_required
def skip_personal_info():
    return redirect(url_for("dashboard"))


@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    old_user = session["username"]
    new_user = request.form.get("new_username", "").strip()
    new_pass = request.form.get("new_password", "")
    if not new_user:
        flash(localized_text("Username cannot be blank.", "उपयोगकर्ता नाम खाली नहीं हो सकता।"), "error")
        return redirect(url_for("dashboard"))
    conn = get_db_connection()
    try:
        if new_pass:
            conn.execute("UPDATE users SET username=?, password=? WHERE username=?",
                         (new_user, generate_password_hash(new_pass), old_user))
        else:
            conn.execute("UPDATE users SET username=? WHERE username=?", (new_user, old_user))
        for table in ["scan_history", "personal_info", "diary_notes", "water_logs"]:
            conn.execute(f"UPDATE {table} SET username=? WHERE username=?", (new_user, old_user))
        conn.commit()
        session["username"] = new_user
        flash(localized_text("Account details updated successfully.", "खाते की जानकारी सफलतापूर्वक अपडेट हो गई है।"), "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash(localized_text("That username is already in use.", "यह उपयोगकर्ता नाम पहले से उपयोग में है।"), "error")
    finally:
        conn.close()
    return redirect(url_for("dashboard"))


# ---------------- DASHBOARD ----------------
@app.route("/search")
@login_required
def global_search():
    q = str(request.args.get("q", "")).strip().lower()
    catalog = [
        ("Meal Scan", "Analyze a meal photo, camera capture or food name.", "meal_scan", "fa-camera"),
        ("Packed Food", "Read packaged-food ingredients and nutrition information.", "packed_food", "fa-box-open"),
        ("Compare Products", "Compare two to four food products.", "compare_food", "fa-code-compare"),
        ("Fitness & Scale", "BMI, calorie, water, steps and workout guidance.", "fitness_scale", "fa-dumbbell"),
        ("Diary", "Food history, notes, trends and reports.", "diary", "fa-book-medical"),
        ("Allergy Alert", "Check ingredients against your saved allergies.", "allergy_check", "fa-shield-heart"),
        ("Edit Profile", "Update personal information, goals, diet and allergies.", "personal_info", "fa-user-pen"),
    ]
    if not q:
        return jsonify({"ok": True, "results": []})
    results=[]
    for title, desc, endpoint, icon in catalog:
        hay=(title+" "+desc).lower()
        if q in hay:
            results.append({"title": localized_text(title, {
                "Meal Scan":"मील स्कैन", "Packed Food":"पैकेज्ड फूड", "Compare Products":"उत्पाद तुलना",
                "Fitness & Scale":"फिटनेस और स्केल", "Diary":"डायरी", "Allergy Alert":"एलर्जी अलर्ट", "Edit Profile":"प्रोफाइल संपादित करें"
            }.get(title,title)), "description": localized_text(desc, desc), "url": url_for(endpoint), "icon": icon})
    return jsonify({"ok": True, "results": results[:8]})

@app.route("/dashboard")
@login_required
def dashboard():
    user = session["username"]
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM scan_history WHERE username=? ORDER BY id DESC LIMIT 6", (user,)).fetchall()
    info = conn.execute("SELECT * FROM personal_info WHERE username=?", (user,)).fetchone()
    today = datetime.now().strftime("%Y-%m-%d")
    water_today = conn.execute(
        "SELECT COALESCE(SUM(liters),0) AS total FROM water_logs WHERE username=? AND date_added LIKE ?",
        (user, today + "%")
    ).fetchone()["total"]
    conn.close()
    return render_template("dashboard.html", history_data=logs, info=dict(info) if info else None,
                           water_today=round(float(water_today or 0), 2), health_tip=random_health_tip(),
                           safety_class=safety_class)


# ---------------- MEAL SCAN ----------------
def meal_api_or_fallback(saved_path, typed_text):
    if saved_path:
        try:
            return analyze_meal_photo(saved_path, current_language()), "service"
        except SmartScanUnavailableError:
            try:
                from dataset_files.predict_helper import predict_food_image
                prediction = predict_food_image(saved_path)
                return get_food_nutrition(prediction["label"]) | {
                    "confidence_note": f"Kaggle fallback confidence: {prediction['confidence']}%"
                }, "kaggle"
            except Exception:
                raise SmartScanUnavailableError("Primary analysis and local fallback both failed.")
    try:
        return analyze_meal_text(typed_text, current_language()), "service"
    except SmartScanUnavailableError:
        text = typed_text.lower()
        for word, category in MEAL_TEXT_KEYWORDS.items():
            if word in text:
                return get_food_nutrition(category), "local"
        raise


@app.route("/meal-scan", methods=["GET", "POST"])
@login_required
def meal_scan():
    user = session["username"]
    result_data = None
    batch_results = []
    if request.method == "POST":
        typed_text = request.form.get("food_text", "").strip()
        camera_string = request.form.get("camera_data", "")
        files = [f for f in request.files.getlist("food_images") if f and f.filename]
        saved_paths = []
        try:
            if camera_string and "," in camera_string:
                saved_paths.append(save_camera_capture(camera_string, "meal"))
            for f in files[:3]:
                saved_paths.append(save_uploaded_file(f, "meal"))
        except (ValueError, OSError):
            flash(localized_text("The image could not be processed. Please try again.", "इमेज प्रोसेस नहीं हो सकी। कृपया फिर से प्रयास करें।"), "error")
            saved_paths = []

        if not saved_paths and not typed_text:
            flash(localized_text("Upload or capture a food photo, or enter the food name.", "भोजन की फोटो अपलोड या कैप्चर करें, या भोजन का नाम लिखें।"), "error")
        else:
            targets = saved_paths if saved_paths else [None]
            info = get_personal_info(user)
            for path in targets:
                try:
                    result, source = meal_api_or_fallback(path, typed_text)
                except SmartScanUnavailableError:
                    flash(localized_text("The food could not be identified. Try a clearer photo or a specific food name.", "भोजन की पहचान नहीं हो सकी। साफ़ फोटो या सही भोजन का नाम आज़माएँ।"), "error")
                    continue
                result["scanned_pic"] = public_path(path) if path else ""
                result["source"] = source
                if source == "gemini":
                    try:
                        result["nutrition_reference"] = verify_nutrition(result.get("food_name", ""), result)
                    except Exception:
                        result["nutrition_reference"] = {"available": False, "source": "USDA FoodData Central"}
                result["safety_class"] = safety_class(result.get("safety_status"))
                result["goal_note"] = get_goal_note(result, info)
                result["personal_alert"] = ""
                terms = list(result.get("ingredients_or_components") or [])
                matches = allergy_matches(info, result.get("food_name"), terms)
                if matches:
                    result["personal_alert"] = (
                        "Allergy Alert: saved allergy match found — " + ", ".join(matches) +
                        ". Please avoid it or check the label carefully."
                    )
                record_scan(user, result["food_name"], result["scanned_pic"], "meal",
                            result.get("calories", 0), result.get("safety_status", ""), source)
                batch_results.append(result)
            if batch_results:
                result_data = batch_results[0]
    return render_template("meal_scan.html", result=result_data, batch_results=batch_results)


# ---------------- PACKED FOOD ----------------
@app.route("/packed-food", methods=["GET", "POST"])
@login_required
def packed_food():
    user = session["username"]
    result_data = None
    if request.method == "POST":
        typed = request.form.get("ingredient_text", "").strip()
        file = request.files.get("packed_image")
        camera = request.form.get("camera_data", "")
        saved_path = None
        try:
            if camera and "," in camera:
                saved_path = save_camera_capture(camera, "packed")
            elif file and file.filename:
                saved_path = save_uploaded_file(file, "packed")
        except (ValueError, OSError):
            flash(localized_text("The image could not be processed.", "इमेज प्रोसेस नहीं हो सकी।"), "error")
        if not typed and not saved_path:
            flash(localized_text("Enter ingredients or upload/capture a label photo.", "सामग्री लिखें या लेबल की फोटो अपलोड/कैप्चर करें।"), "error")
        else:
            try:
                if typed:
                    result_data = analyze_packed_food_text(typed, current_language())
                    source = "gemini"
                else:
                    result_data = analyze_packed_food(saved_path, current_language())
                    source = "gemini"
            except SmartScanUnavailableError:
                source = "local"
                text = typed or read_text_from_image(saved_path)
                risks = [{"ingredient": k, "reason": v} for k, v in RISKY_INGREDIENT_LIST.items() if k in text.lower()]
                result_data = {
                    "product_name": "Scanned/Typed Product",
                    "ingredients_found": text.split(",")[:20] if text else [],
                    "risks": risks,
                    "verdict": "Safe in moderation" if not risks else "Limit this product",
                    "details": [
                        "The local label-reading fallback was used.",
                        "Only ingredients that could be matched were flagged.",
                        "A missing match does not prove a product is medically safe.",
                        "Check the full label and nutrition panel before regular use.",
                        "Keep portions sensible and vary your food choices.",
                    ],
                    "confidence_note": "Local fallback — label reading may be incomplete."
                }
            if source == "gemini":
                try:
                    result_data = enrich_packed_result(result_data)
                except Exception:
                    pass
            result_data["scanned_pic"] = public_path(saved_path) if saved_path else ""
            result_data["safety_class"] = safety_class(result_data.get("verdict"))
            info = get_personal_info(user)
            matches = allergy_matches(
                info, result_data.get("product_name"),
                list(result_data.get("ingredients_found") or []) +
                [r.get("ingredient", "") for r in result_data.get("risks", [])]
            )
            result_data["personal_alert"] = (
                "Allergy Alert: saved allergy match found — " + ", ".join(matches) +
                ". Please check the label carefully before using this product."
            ) if matches else ""
            record_scan(user, result_data["product_name"], result_data["scanned_pic"], "packed",
                        0, result_data.get("verdict", ""), source)
    return render_template("packed_food.html", result=result_data)


# ---------------- COMPARE ----------------
@app.route("/compare-food", methods=["GET", "POST"])
@login_required
def compare_food():
    user = session["username"]
    comparison_result = None
    if request.method == "POST":
        saved_paths = []
        for slot in ["food_image_1", "food_image_2", "food_image_3", "food_image_4"]:
            f = request.files.get(slot)
            if f and f.filename:
                try:
                    saved_paths.append(save_uploaded_file(f, "compare"))
                except OSError:
                    pass
        if len(saved_paths) < 2:
            flash(localized_text("Please provide at least two product photos.", "कम से कम दो उत्पादों की फोटो दें।"), "error")
        else:
            try:
                comparison_result = compare_products_smart(saved_paths, current_language())
                source = "gemini"
            except SmartScanUnavailableError:
                comparison_result = compare_products(saved_paths)
                source = "local"
                for p in comparison_result.get("products", []):
                    p.setdefault("details", [])
            info = get_personal_info(user)
            for i, product in enumerate(comparison_result.get("products", [])):
                if i < len(saved_paths):
                    product["scanned_pic"] = public_path(saved_paths[i])
                product["safety_class"] = safety_class(
                    " ".join(r.get("reason", "") for r in product.get("risky_ingredients", []))
                )
                terms = list(product.get("ingredients_found") or []) + [
                    r.get("ingredient", "") for r in product.get("risky_ingredients", [])
                ]
                matches = allergy_matches(info, product.get("product_name"), terms)
                product["personal_alert"] = (
                    "Allergy Alert: " + ", ".join(matches) if matches else ""
                )
                record_scan(user, product.get("product_name", f"Product {i+1}"),
                            product.get("scanned_pic", ""), "compare", 0,
                            "Risk flags found" if product.get("risky_ingredients") else "No major risk flags returned",
                            source)
            best = comparison_result.get("best_index")
            if isinstance(best, int) and 0 <= best < len(comparison_result.get("products", [])):
                comparison_result["products"][best]["recommended"] = True
    return render_template("compare_food.html", result=comparison_result)


# ---------------- FITNESS ----------------
@app.route("/fitness-scale", methods=["GET", "POST"])
@login_required
def fitness_scale():
    result = None
    calc_type = None
    user = session["username"]
    if request.method == "POST":
        calc_type = request.form.get("calc_type")
        try:
            if calc_type == "bmi":
                w, h = float(request.form["weight"]), float(request.form["height"])
                if w <= 0 or h <= 0: raise ValueError
                bmi, category = calculate_bmi(w, h)
                result = {"bmi": bmi, "category": category}
            elif calc_type == "calorie":
                w, h, age = float(request.form["weight"]), float(request.form["height"]), float(request.form["age"])
                if min(w, h, age) <= 0: raise ValueError
                result = {"daily_calories": calculate_calorie_need(
                    request.form.get("gender", "Male"), w, h, age,
                    request.form.get("activity_level", ACTIVITY_LEVEL_LIST[0])
                )}
            elif calc_type == "water":
                w = float(request.form["weight"])
                if w <= 0: raise ValueError
                liters = calculate_water_intake(w)
                result = {"water_liters": liters}
                conn = get_db_connection()
                conn.execute("INSERT INTO water_logs (username, liters, date_added) VALUES (?, ?, ?)",
                             (user, liters, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit(); conn.close()
            elif calc_type == "steps":
                result = {"step_goal": calculate_step_goal(request.form.get("goal_type", GOAL_TYPE_LIST[-1]))}
        except (ValueError, KeyError):
            flash(localized_text("Please enter valid positive numbers.", "कृपया सही धनात्मक संख्याएँ दर्ज करें।"), "error")
    return render_template("fitness_scale.html", result=result, calc_type=calc_type,
                           activity_list=ACTIVITY_LEVEL_LIST, goal_list=GOAL_TYPE_LIST,
                           workout_suggestions={
                               "Fat Loss & Lean Body": ["Brisk walking", "Bodyweight circuit", "Cycling"],
                               "Muscle Building": ["Squats", "Push-ups", "Rows or resistance-band pulls"],
                               "Stamina & Endurance": ["Jog/walk intervals", "Cycling", "Light running"],
                               "General Wellness": ["Full-body mobility", "Walking", "Light strength training"],
                           })


# ---------------- DIARY / REPORT ----------------
@app.route("/diary", methods=["GET", "POST"])
@login_required
def diary():
    user = session["username"]
    conn = get_db_connection()
    if request.method == "POST":
        note = request.form.get("note_text", "").strip()
        mood = request.form.get("mood", "Neutral")
        if note:
            conn.execute("INSERT INTO diary_notes (username,note_text,mood,date_added) VALUES (?,?,?,?)",
                         (user, note, mood, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
    category = request.args.get("category", "").strip().lower()
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    query = "SELECT * FROM scan_history WHERE username=?"
    params = [user]
    if category in {"meal", "packed", "compare"}:
        query += " AND category=?"; params.append(category)
    if start:
        query += " AND substr(date_added,1,10)>=?"; params.append(start)
    if end:
        query += " AND substr(date_added,1,10)<=?"; params.append(end)
    query += " ORDER BY id DESC"
    logs = conn.execute(query, params).fetchall()
    notes = conn.execute("SELECT * FROM diary_notes WHERE username=? ORDER BY id DESC", (user,)).fetchall()
    chart_rows = conn.execute("""
        SELECT substr(date_added,1,10) AS day,
               ROUND(COALESCE(SUM(calories),0),1) AS calories
        FROM scan_history WHERE username=? GROUP BY day ORDER BY day DESC LIMIT 7
    """, (user,)).fetchall()
    water_rows = conn.execute("""
        SELECT substr(date_added,1,10) AS day, ROUND(SUM(liters),2) AS water
        FROM water_logs WHERE username=? GROUP BY day ORDER BY day DESC LIMIT 7
    """, (user,)).fetchall()
    conn.close()
    chart = {
        "labels": [r["day"] for r in reversed(chart_rows)],
        "calories": [float(r["calories"] or 0) for r in reversed(chart_rows)],
        "water": [next((float(w["water"]) for w in water_rows if w["day"] == r["day"]), 0)
                  for r in reversed(chart_rows)]
    }
    return render_template("diary.html", notes=notes, logs=logs, chart=chart,
                           selected_category=category, start=start, end=end)


@app.route("/diary/delete/<int:note_id>")
@login_required
def diary_delete(note_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM diary_notes WHERE id=? AND username=?", (note_id, session["username"]))
    conn.commit(); conn.close()
    return redirect(url_for("diary"))


@app.route("/diary/delete-log/<int:log_id>")
@login_required
def diary_delete_log(log_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM scan_history WHERE id=? AND username=?", (log_id, session["username"]))
    conn.commit(); conn.close()
    return redirect(url_for("diary"))


@app.route("/diary/report")
@login_required
def diary_report():
    # ReportLab is deliberately used so the report works without a browser printer.
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm

    user = session["username"]
    conn = get_db_connection()
    info = get_personal_info(user) or {}
    logs = conn.execute("SELECT * FROM scan_history WHERE username=? ORDER BY id DESC", (user,)).fetchall()
    water = conn.execute("SELECT * FROM water_logs WHERE username=? ORDER BY id DESC LIMIT 30", (user,)).fetchall()
    conn.close()
    report_path = os.path.join(UPLOAD_FOLDER, f"NutriFood_Report_{secrets.token_hex(5)}.pdf")
    doc = SimpleDocTemplate(report_path, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=14*mm, bottomMargin=14*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("NFTitle", parent=styles["Title"], textColor=colors.HexColor("#6f42c1"))
    story = [Paragraph("NutriFood Health — Personal Report", title),
             Paragraph(f"User: {user}", styles["Normal"]), Spacer(1, 8)]
    if info:
        story.append(Paragraph(
            f"Goal: {info.get('goal_type','Not set')} | Diet: {info.get('diet_type','Not set')} | "
            f"Allergies: {info.get('allergies','None saved')}", styles["Normal"]))
        story.append(Spacer(1, 10))
    data = [["Date", "Type", "Item", "Calories", "Status"]]
    for r in logs:
        data.append([r["date_added"], str(r["category"]).title(), r["food_name"],
                     str(round(float(r["calories"] or 0), 1)), r["safety_status"] or "—"])
    if len(data) == 1:
        data.append(["—", "—", "No scan history", "0", "—"])
    table = Table(data, repeatRows=1, colWidths=[30*mm, 20*mm, 58*mm, 22*mm, 50*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#6f42c1")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cccccc")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f5f2fa")]),
    ]))
    story += [Paragraph("Scan History", styles["Heading2"]), table, Spacer(1, 12),
              Paragraph("Recent Water Entries", styles["Heading2"])]
    wdata = [["Date", "Litres"]] + [[w["date_added"], str(w["liters"])] for w in water]
    if len(wdata) == 1: wdata.append(["—", "No water entries"])
    wt = Table(wdata, repeatRows=1, colWidths=[70*mm, 30*mm])
    wt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#6f42c1")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cccccc")),
        ("FONTSIZE",(0,0),(-1,-1),8),
    ]))
    story.append(wt)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Note: nutrition and food-safety outputs are estimates and should not be treated as medical diagnosis.", styles["Italic"]))
    doc.build(story)
    return send_file(report_path, as_attachment=True, download_name="NutriFood_Health_Report.pdf")


# ---------------- ALLERGY ----------------
@app.route("/allergy-check", methods=["GET", "POST"])
@login_required
def allergy_check():
    user = session["username"]
    info = get_personal_info(user)
    saved = safe_allergies(info)
    result = None
    if request.method == "POST":
        text = request.form.get("food_text", "").strip()
        matches = allergy_matches(info, text)
        if not saved:
            result = {"type":"info", "message":"Profile mein allergy save nahi hai. Personal Info se add karo."}
        elif matches:
            result = {"type":"danger", "message":"Allergy match: " + ", ".join(matches) + ". Ingredient/food ko avoid ya carefully verify karo."}
        else:
            result = {"type":"safe", "message":"Saved allergies ke saath koi text match nahi mila."}
    return render_template("allergy_check.html", result=result, saved_allergies=saved, common_allergens=COMMON_ALLERGENS)


# ---------------- ADMIN STATS ----------------
def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "username" not in session or session["username"].lower() != ADMIN_USERNAME.lower():
            flash("Admin Stats sirf configured admin account ke liye available hai.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapper


@app.route("/admin-stats")
@login_required
@admin_required
def admin_stats():
    conn = get_db_connection()
    users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    scans = conn.execute("SELECT COUNT(*) AS n FROM scan_history").fetchone()["n"]
    meals = conn.execute("SELECT COUNT(*) AS n FROM scan_history WHERE category='meal'").fetchone()["n"]
    packed = conn.execute("SELECT COUNT(*) AS n FROM scan_history WHERE category='packed'").fetchone()["n"]
    compares = conn.execute("SELECT COUNT(*) AS n FROM scan_history WHERE category='compare'").fetchone()["n"]
    notes = conn.execute("SELECT COUNT(*) AS n FROM diary_notes").fetchone()["n"]
    conn.close()
    return render_template("admin_stats.html", stats={
        "users":users, "scans":scans, "meals":meals, "packed":packed, "compares":compares, "notes":notes
    })


# ---------------- CHATBOT / TRANSLATION ----------------
@app.route("/api/speak", methods=["POST"])
@login_required
def api_speak():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    language = str(payload.get("language", current_language()))
    if not text:
        return jsonify({"ok": False, "error": "No text supplied."}), 400
    try:
        audio = synthesize_speech(text, language)
        return send_file(__import__("io").BytesIO(audio), mimetype="audio/wav", as_attachment=False, download_name="answer.wav")
    except SmartScanUnavailableError:
        return jsonify({"ok": False, "error": localized_text("Voice generation is unavailable right now.", "अभी आवाज़ तैयार नहीं हो सकी।")}), 503


@app.route("/api/transcribe", methods=["POST"])
@login_required
def api_transcribe():
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"ok": False, "error": localized_text("No audio was received.", "कोई ऑडियो नहीं मिला।")}), 400
    try:
        raw = audio.read()
        if not raw:
            raise SmartScanUnavailableError("Empty audio.")
        if len(raw) > 12 * 1024 * 1024:
            return jsonify({"ok": False, "error": localized_text("The recording is too large.", "रिकॉर्डिंग बहुत बड़ी है।")}), 413
        transcript = transcribe_audio(raw, audio.content_type or "audio/webm", current_language())
        return jsonify({"ok": True, "text": transcript})
    except SmartScanUnavailableError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    history = []
    page_image = ""
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        message = str(request.form.get("message", "")).strip()
        context = str(request.form.get("context", "General")).strip()
        chat_image = request.files.get("image")
        page_image = str(request.form.get("page_image", "")).strip()
        try:
            import json as _json
            history = _json.loads(request.form.get("history", "[]"))
        except Exception:
            history = []
    else:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        context = str(payload.get("context", "General")).strip()
        history = payload.get("history") or []
        chat_image = None
        page_image = str(payload.get('page_image', '')).strip()
    chat_image_path = None
    if chat_image and chat_image.filename:
        try:
            chat_image_path = save_uploaded_file(chat_image, "chat")
        except Exception:
            return jsonify({"ok": False, "answer": localized_text("The image could not be uploaded.", "इमेज अपलोड नहीं हो सकी।")}), 400
    # Reuse the currently displayed scan image for follow-up questions, without requiring re-upload.
    if not chat_image_path and page_image.startswith('/static/uploads/'):
        candidate = os.path.normpath(os.path.join(BASE_DIR, page_image.lstrip('/').replace('/', os.sep)))
        upload_root = os.path.normpath(UPLOAD_FOLDER)
        if candidate.startswith(upload_root + os.sep) and os.path.isfile(candidate):
            chat_image_path = candidate
    if not message and not chat_image_path:
        return jsonify({"ok": False, "answer": localized_text("Enter a question or attach an image.", "प्रश्न लिखें या इमेज जोड़ें।")}), 400
    if len(message) > 1000:
        return jsonify({"ok": False, "answer": localized_text("Please keep the question within 1000 characters.", "कृपया प्रश्न 1000 अक्षरों के भीतर रखें।")}), 400
    try:
        answer = chat_with_gemini(message, context, get_personal_info(session["username"]), language=current_language(), image_path=chat_image_path, history=history)
        return jsonify({"ok": True, "answer": answer})
    except SmartScanUnavailableError as exc:
        # Never replace a real Gemini answer with a canned generic answer.
        # The client will show a clear retry message if Gemini itself is unavailable.
        return jsonify({
            "ok": False,
            "answer": localized_text(
                "The assistant could not reach the answer service. Please try again in a moment.",
                "सहायक अभी उत्तर सेवा से जुड़ नहीं सका। कृपया थोड़ी देर बाद फिर प्रयास करें।"
            ),
            "error": str(exc)
        }), 503


@app.route("/api/translate-batch", methods=["POST"])
@login_required
def api_translate_batch():
    payload = request.get_json(silent=True) or {}
    texts = payload.get("texts") or []
    if not isinstance(texts, list) or len(texts) > 120:
        return jsonify({"ok": False}), 400
    clean = [str(x)[:500] for x in texts]
    if current_language() == "English":
        return jsonify({"ok": True, "translations": clean})
    try:
        from python_files.smart_scan_helper import translate_batch
        return jsonify({"ok": True, "translations": translate_batch(clean, "Hindi")})
    except SmartScanUnavailableError:
        return jsonify({"ok": True, "translations": clean, "offline": True})

@app.route("/api/translate", methods=["POST"])
@login_required
def api_translate():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    target = set_language(payload.get("target", "Hindi"))
    if not text:
        return jsonify({"ok": False}), 400
    if target == "English":
        return jsonify({"ok": True, "translation": text})
    try:
        return jsonify({"ok": True, "translation": translate_text(text, "Hindi")})
    except SmartScanUnavailableError:
        return jsonify({"ok": True, "translation": text, "source": "offline"})


@app.errorhandler(413)
def too_large(_):
    flash(localized_text("Images must be smaller than 12 MB.", "इमेज 12 MB से छोटी होनी चाहिए।"), "error")
    return redirect(request.referrer or url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
