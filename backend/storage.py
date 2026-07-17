"""
storage.py
----------
A tiny JSON-file "database" so the whole project can run instantly
with zero setup (no PostgreSQL/MongoDB server needed). Every function
here reads a JSON file, changes it, and writes it back.

This is intentionally simple for learning/demo purposes. For a real
production app you would swap this file out for SQLAlchemy models
backed by PostgreSQL, but every other file only talks to the
functions below, so that swap would not require changing any routes.
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")
MATERIALS_FILE = os.path.join(DATA_DIR, "materials.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------- Users ----------

def get_users():
    return _load(USERS_FILE, {})


def create_user(username, password):
    users = get_users()
    if username in users:
        return False, "That username is already taken."
    users[username] = {"password": password, "created_at": datetime.utcnow().isoformat()}
    _save(USERS_FILE, users)
    return True, "Account created."


def check_login(username, password):
    users = get_users()
    user = users.get(username)
    if not user or user["password"] != password:
        return False
    return True


# ---------- Study materials ----------

def save_material(username, material_id, filename, text):
    materials = _load(MATERIALS_FILE, {})
    materials.setdefault(username, {})
    materials[username][material_id] = {
        "filename": filename,
        "text": text,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    _save(MATERIALS_FILE, materials)


def get_material(username, material_id):
    materials = _load(MATERIALS_FILE, {})
    return materials.get(username, {}).get(material_id)


def list_materials(username):
    materials = _load(MATERIALS_FILE, {})
    user_materials = materials.get(username, {})
    return [
        {"id": mid, "filename": m["filename"], "uploaded_at": m["uploaded_at"]}
        for mid, m in user_materials.items()
    ]


# ---------- Progress tracking ----------

def get_progress(username):
    progress = _load(PROGRESS_FILE, {})
    return progress.get(username, {
        "quiz_scores": [],       # list of {topic, score, total, date}
        "topics_completed": [],  # list of topic names
        "study_streak": 0,
        "last_study_date": None,
    })


def record_quiz_score(username, topic, score, total):
    progress = _load(PROGRESS_FILE, {})
    user_progress = progress.get(username, {
        "quiz_scores": [], "topics_completed": [], "study_streak": 0, "last_study_date": None
    })
    user_progress["quiz_scores"].append({
        "topic": topic, "score": score, "total": total,
        "date": datetime.utcnow().isoformat(),
    })
    _update_streak(user_progress)
    progress[username] = user_progress
    _save(PROGRESS_FILE, progress)
    return user_progress


def mark_topic_complete(username, topic):
    progress = _load(PROGRESS_FILE, {})
    user_progress = progress.get(username, {
        "quiz_scores": [], "topics_completed": [], "study_streak": 0, "last_study_date": None
    })
    if topic not in user_progress["topics_completed"]:
        user_progress["topics_completed"].append(topic)
    _update_streak(user_progress)
    progress[username] = user_progress
    _save(PROGRESS_FILE, progress)
    return user_progress


def _update_streak(user_progress):
    today = datetime.utcnow().date().isoformat()
    last = user_progress.get("last_study_date")
    if last == today:
        pass  # already studied today, streak unchanged
    elif last is None:
        user_progress["study_streak"] = 1
    else:
        last_date = datetime.fromisoformat(last).date()
        gap = (datetime.utcnow().date() - last_date).days
        user_progress["study_streak"] = user_progress["study_streak"] + 1 if gap == 1 else 1
    user_progress["last_study_date"] = today


def weak_topics(username, threshold=0.6):
    """Return topics where the average quiz score is below `threshold`."""
    progress = get_progress(username)
    totals = {}
    for entry in progress["quiz_scores"]:
        t = entry["topic"]
        totals.setdefault(t, {"score": 0, "total": 0})
        totals[t]["score"] += entry["score"]
        totals[t]["total"] += entry["total"]
    weak = []
    for topic, vals in totals.items():
        if vals["total"] > 0 and (vals["score"] / vals["total"]) < threshold:
            weak.append(topic)
    return weak
