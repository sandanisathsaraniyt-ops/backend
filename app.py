from flask import Flask, request, jsonify
from datetime import datetime
from flask_cors import CORS
import hashlib
import re
import random
import urllib.parse

from database import get_db_connection, save_activity_result

app = Flask(__name__)
CORS(app)

# ================= PASSWORD =================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

    # ================= EMAIL VALIDATION =================
def is_valid_email(email):
    # Only allow @gmail.com
    return re.match(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", email)

# ================= USERNAME SUGGESTIONS =================
def suggest_usernames(base, cursor):
    suggestions = []
    while len(suggestions) < 5:
        suffix = random.randint(100, 9999)
        new_name = f"{base}{suffix}"
        cursor.execute("SELECT 1 FROM responsible_adult WHERE username = ?", (new_name,))
        if not cursor.fetchone():
            suggestions.append(new_name)
    return suggestions

# ================= SIGNUP =================
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")

    if not all([email, username, password]):
        return jsonify({"error": "All fields required"}), 400

    # Email format check
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format. Use @gmail.com only"}), 400

    # Password strength check
    if not is_valid_password(password):
        return jsonify({
            "error": "Weak password. Must include uppercase, lowercase, number, symbol, and be 8+ chars"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Duplicate email
    cursor.execute("SELECT 1 FROM responsible_adult WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Email already exists"}), 409

    # Duplicate username
    cursor.execute("SELECT 1 FROM responsible_adult WHERE username = ?", (username,))
    if cursor.fetchone():
        suggestions = suggest_usernames(username, cursor)
        conn.close()
        return jsonify({"error": "Username exists", "suggestions": suggestions}), 409

    # Insert user
    cursor.execute("""
        INSERT INTO responsible_adult (email, username, password_hash)
        VALUES (?, ?, ?)
    """, (email, username, hash_password(password)))

    conn.commit()
    conn.close()
    return jsonify({"message": "Signup successful"}), 201

# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password_hash FROM responsible_adult WHERE email = ?",
        (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user or user["password_hash"] != hash_password(password):
        return jsonify({"error": "Invalid login"}), 401

    return jsonify({"message": "Login successful"}), 200

# ================= ADD CHILD =================
@app.route("/add-child", methods=["POST"])
def add_child():
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT adult_id FROM responsible_adult WHERE email = ?",
        (data["email"],)
    )
    adult = cursor.fetchone()

    if not adult:
        conn.close()
        return jsonify({"error": "Adult not found"}), 404

    cursor.execute("""
        INSERT INTO child (adult_id, child_name, gender, age, grade)
        VALUES (?, ?, ?, ?, ?)
    """, (
        adult["adult_id"],
        data["name"],
        data["gender"],
        data["age"],
        data["grade"]
    ))

    conn.commit()
    conn.close()
    return jsonify({"message": "Child added"}), 201

# ================= SAVE ACTIVITY =================
@app.route('/save-activity', methods=['POST'])
def save_activity():
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT child_id FROM child WHERE child_name = ?",
        (data["child_name"],)
    )
    child = cursor.fetchone()

    if not child:
        conn.close()
        return jsonify({"error": "Child not found"}), 404

    activity_id = data["activity_id"]
    given = data.get("given_answer")

    # ---------- CORRECT ANSWERS ----------
    correct_answers = {
        1: "5",
        2: "<",
        3: "7",
        4: "නැත",
        5: "7",
        6: "3",
        7: "1",
        8: "1",
        9: "-",
        11: "1",
        13: "1",  
    }

    score = 0
    is_correct = 0

    # ---------- ACTIVITY 10 ----------
    if activity_id == 10:
        correct_set = {"0", "8"}
        if not given:
            score = 0
        elif set(given.split(",")) == correct_set:
            score = 1
            is_correct = 1
        else:
            score = -1

    # ---------- ACTIVITY 12 ----------
    elif activity_id == 12:
        if not given:
            score = 0
        elif given == "3":
            score = 1
            is_correct = 1
        else:
            score = -1

    # ---------- NORMAL ----------
    else:
        if not given:
            score = 0
        elif given == correct_answers.get(activity_id):
            score = 1
            is_correct = 1
        else:
            score = -1

    save_activity_result(
        child["child_id"],
        activity_id,
        given,
        is_correct,
        score,
        1,
        data["time_taken_seconds"]
    )

    conn.close()
    return jsonify({"message": "Saved"}), 200

# ================= FEATURE EXTRACTION =================
def calculate_features(activity_rows):
    correct = sum(1 for a in activity_rows if a["score"] == 1)
    wrong = sum(1 for a in activity_rows if a["score"] == -1)
    skipped = sum(1 for a in activity_rows if a["score"] == 0)

    total = correct + wrong + skipped

    avg_time = (
        sum(a["time_taken_seconds"] or 0 for a in activity_rows) / total
        if total else 0
    )

    return {
        "accuracy": correct / total if total else 0,
        "skip_rate": skipped / total if total else 0,
        "avg_time": avg_time,
        "wrong": wrong,
        "skipped": skipped,
        "total": total
    }

# ================= HELPER =================
def filter_activities(activities, start_id, end_id):
    return [a for a in activities if start_id <= a["activity_id"] <= end_id]

# ================= ML MODELS =================
def ml_model_1_dyscalculia(activity_rows):
    if not activity_rows:
        return None, "Not Enough Data"

    f = calculate_features(activity_rows)
    accuracy = f["accuracy"]
    skip_rate = f["skip_rate"]
    avg_time = f["avg_time"]
    wrong_skipped_ratio = (f["wrong"] + f["skipped"]) / f["total"]

    if accuracy < 0.4 or wrong_skipped_ratio >= 0.5 or skip_rate >= 0.3 or avg_time >= 8:
        return 0.85, "High Risk"
    if accuracy < 0.7 or skip_rate >= 0.15 or avg_time >= 5:
        return 0.55, "Mild Risk"

    return 0.15, "No Risk"

def ml_model_2_attention(activity_rows):
    if len(activity_rows) < 2:
        return "Not Enough Data"

    if any(a["score"] != 1 for a in activity_rows):
        return "Attention Impairment"

    return "No Attention Impairment"

def ml_model_3_memory(activity_rows):
    if len(activity_rows) < 2:
        return "Not Enough Data"

    if any(a["score"] != 1 for a in activity_rows):
        return "Memory Impairment"

    return "No Memory Impairment"

# ================= VIEW REPORT =================
@app.route("/view-report/<child_name>", methods=["GET"])
def view_report(child_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT child_id, child_name, age, gender
        FROM child WHERE child_name = ?
    """, (child_name,))
    child = cursor.fetchone()

    if not child:
        conn.close()
        return jsonify({"error": "Child not found"}), 404

    cursor.execute("""
        SELECT activity_id, given_answer, is_correct, score, time_taken_seconds
        FROM activity_results
        WHERE child_id = ?
        ORDER BY activity_id
    """, (child["child_id"],))
    activities = cursor.fetchall()

    dys_data = filter_activities(activities, 1, 9)
    att_data = filter_activities(activities, 10, 11)
    mem_data = filter_activities(activities, 12, 13)

    _, dys_result = ml_model_1_dyscalculia(dys_data)
    attention_result = ml_model_2_attention(att_data)
    memory_result = ml_model_3_memory(mem_data)

    return jsonify({
        "child": dict(child),
        "activities": [dict(a) for a in activities],
        "dyscalculia_risk": dys_result,
        "attention_status": attention_result,
        "memory_status": memory_result
    }), 200

# ================= CHILD LIST =================
@app.route("/children/<path:parent_email>", methods=["GET"])
def get_children(parent_email):
    parent_email = urllib.parse.unquote(parent_email)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT adult_id FROM responsible_adult WHERE email = ?",
        (parent_email,)
    )
    adult = cursor.fetchone()

    if not adult:
        conn.close()
        return jsonify([]), 200

    cursor.execute(
        "SELECT child_name FROM child WHERE adult_id = ?",
        (adult["adult_id"],)
    )

    children = [row["child_name"] for row in cursor.fetchall()]
    conn.close()

    return jsonify(children), 200

# ================= TEST =================
@app.route("/")
def home():
    return "API running", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)