import os
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv

from agents import generate_gymbuddy_reply, build_profile_summary

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")


# -------- Helpers -------- #
def _sanitize_int(value: Any, default: int | None = None, min_v: int | None = None, max_v: int | None = None) -> int | None:
    try:
        iv = int(value)
        if min_v is not None and iv < min_v:
            iv = min_v
        if max_v is not None and iv > max_v:
            iv = max_v
        return iv
    except Exception:
        return default


def _bool_from_any(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


# -------- Routes -------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/onboarding", methods=["POST"])
def onboarding():
    data: Dict[str, Any] = request.get_json(silent=True) or {}

    profile = {
        "weight_kg": _sanitize_int(data.get("weight_kg"), None, 30, 300),
        "height_cm": _sanitize_int(data.get("height_cm"), None, 120, 230),
        "age": _sanitize_int(data.get("age"), None, 10, 100),
        "gender": (data.get("gender") or "").strip().lower(),
        "main_goal": (data.get("main_goal") or "").strip().lower(),
        "experience": (data.get("experience") or "").strip().lower(),
        "days_per_week": _sanitize_int(data.get("days_per_week"), None, 1, 7),
        "minutes_per_workout": _sanitize_int(data.get("minutes_per_workout"), None, 20, 180),
        "injuries_yes_no": _bool_from_any(data.get("injuries_yes_no")),
        "injuries_details": (data.get("injuries_details") or "").strip(),
    }

    # Minimal validation: require goal and experience and days
    required = ["weight_kg", "height_cm", "age", "gender", "main_goal", "experience", "days_per_week", "minutes_per_workout"]
    missing = [k for k in required if not profile.get(k)]
    if missing:
        return jsonify({"ok": False, "error": f"Missing or invalid fields: {', '.join(missing)}"}), 400

    session["profile"] = profile
    summary = build_profile_summary(profile)
    return jsonify({"ok": True, "profile": profile, "profile_summary": summary})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    prof = session.get("profile")
    if not prof:
        return jsonify({"ok": False, "profile": None}), 200
    return jsonify({"ok": True, "profile": prof, "profile_summary": build_profile_summary(prof)})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Message is required."}), 400

    profile = session.get("profile") or {}
    try:
        reply = generate_gymbuddy_reply(message, profile)
        return jsonify({"ok": True, "reply": reply})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
