from flask import Blueprint, request, jsonify, session
from backend.db import get_cursor
from functools import wraps

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Login required", "redirect": "/login"}), 401
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username aur password required"}), 400

    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()

    if not user or user["password"] != password:
        return jsonify({"error": "Wrong username or password"}), 401

    session["user_id"]   = user["id"]
    session["username"]  = user["username"]
    session["full_name"] = user["full_name"]
    session["role"]      = user["role"]

    return jsonify({
        "message":   "Login successful!",
        "username":  user["username"],
        "full_name": user["full_name"],
        "role":      user["role"]
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@auth_bp.route("/me", methods=["GET"])
def me():
    if not session.get("user_id"):
        return jsonify({"logged_in": False}), 401
    return jsonify({
        "logged_in": True,
        "username":  session.get("username"),
        "full_name": session.get("full_name"),
        "role":      session.get("role")
    })


@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    if not session.get("user_id"):
        return jsonify({"error": "Login required"}), 401
    data     = request.json
    old_pass = data.get("old_password","")
    new_pass = data.get("new_password","")

    with get_cursor() as cur:
        cur.execute("SELECT password FROM users WHERE id=?", (session["user_id"],))
        user = cur.fetchone()

    if user["password"] != old_pass:
        return jsonify({"error": "Old password wrong"}), 401
    if len(new_pass) < 4:
        return jsonify({"error": "Password minimum 4 characters"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE users SET password=? WHERE id=?",
                    (new_pass, session["user_id"]))
    return jsonify({"message": "Password changed!"})