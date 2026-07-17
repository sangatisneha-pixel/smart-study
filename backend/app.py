"""
app.py
------
The Flask API for Smart Study Companion.

Run it with:
    python app.py

Then open frontend/index.html in your browser (or serve it with any
static file server). The frontend talks to this API on
http://localhost:5000.

Each route is deliberately small and does one job, calling out to
nlp_utils.py for the "AI" logic and storage.py for saving data.
"""

import os
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS

import nlp_utils
import storage

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)  # allow the frontend (served from a different port/file) to call this API

@app.route("/")
def index():
    return app.send_static_file("index.html")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(filepath):
    """Pull plain text out of a .txt, .pdf or .docx file."""
    ext = filepath.rsplit(".", 1)[1].lower()

    if ext == "txt":
        with open(filepath, "r", errors="ignore") as f:
            return f.read()

    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == "docx":
        import docx
        doc = docx.Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)

    return ""


# ---------------------------------------------------------------- auth ----

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    success, message = storage.create_user(username, password)
    return jsonify({"success": success, "message": message})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if storage.check_login(username, password):
        return jsonify({"success": True, "message": "Welcome back!"})
    return jsonify({"success": False, "message": "Incorrect username or password."}), 401


# ------------------------------------------------------------- uploads ----

@app.route("/api/upload", methods=["POST"])
def upload():
    username = request.form.get("username", "guest")
    file = request.files.get("file")

    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No file selected."}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Please upload a .txt, .pdf or .docx file."}), 400

    material_id = uuid.uuid4().hex[:10]
    saved_path = os.path.join(UPLOAD_DIR, f"{material_id}_{file.filename}")
    file.save(saved_path)

    text = extract_text(saved_path)
    if not text.strip():
        return jsonify({"success": False, "message": "Couldn't read any text from that file."}), 400

    storage.save_material(username, material_id, file.filename, text)
    return jsonify({
        "success": True,
        "material_id": material_id,
        "filename": file.filename,
        "preview": text[:300],
    })


@app.route("/api/materials/<username>", methods=["GET"])
def materials(username):
    return jsonify({"materials": storage.list_materials(username)})


# --------------------------------------------------------- AI features ----

@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.get_json(force=True)
    text = _get_material_text(data)
    if text is None:
        return jsonify({"success": False, "message": "Material not found."}), 404

    length = data.get("length", "short")  # "short" or "detailed"
    num_sentences = 3 if length == "short" else 8

    return jsonify({
        "success": True,
        "summary": nlp_utils.summarize_text(text, num_sentences),
        "key_points": nlp_utils.extract_key_points(text, 6),
    })


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    text = _get_material_text(data)
    question = data.get("question", "")
    if text is None:
        return jsonify({"success": False, "message": "Material not found."}), 404
    if not question.strip():
        return jsonify({"success": False, "message": "Please type a question."}), 400

    answer = nlp_utils.answer_question(text, question)
    return jsonify({"success": True, "answer": answer})


@app.route("/api/quiz", methods=["POST"])
def quiz():
    data = request.get_json(force=True)
    text = _get_material_text(data)
    if text is None:
        return jsonify({"success": False, "message": "Material not found."}), 404

    num_questions = int(data.get("num_questions", 5))
    return jsonify({"success": True, "quiz": nlp_utils.generate_quiz(text, num_questions)})


@app.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    data = request.get_json(force=True)
    username = data.get("username", "guest")
    topic = data.get("topic", "General")
    score = int(data.get("score", 0))
    total = int(data.get("total", 0))
    progress = storage.record_quiz_score(username, topic, score, total)
    return jsonify({"success": True, "progress": progress})


@app.route("/api/flashcards", methods=["POST"])
def flashcards():
    data = request.get_json(force=True)
    text = _get_material_text(data)
    if text is None:
        return jsonify({"success": False, "message": "Material not found."}), 404

    num_cards = int(data.get("num_cards", 8))
    return jsonify({"success": True, "flashcards": nlp_utils.generate_flashcards(text, num_cards)})


@app.route("/api/planner", methods=["POST"])
def planner():
    data = request.get_json(force=True)
    subjects = data.get("subjects", [])
    hours_per_day = float(data.get("hours_per_day", 2))
    days_until_exam = int(data.get("days_until_exam", 7))

    plan = nlp_utils.generate_study_plan(subjects, hours_per_day, days_until_exam)
    return jsonify({"success": True, "plan": plan})


# ---------------------------------------------------------- progress ------

@app.route("/api/progress/<username>", methods=["GET"])
def progress(username):
    data = storage.get_progress(username)
    data["weak_topics"] = storage.weak_topics(username)
    return jsonify(data)


@app.route("/api/progress/<username>/complete-topic", methods=["POST"])
def complete_topic(username):
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"success": False, "message": "Topic name is required."}), 400
    updated = storage.mark_topic_complete(username, topic)
    return jsonify({"success": True, "progress": updated})


# ------------------------------------------------------------- helpers ----

def _get_material_text(data):
    """Look up material text either from a saved material_id, or raw pasted text."""
    if data.get("text"):
        return data["text"]
    username = data.get("username", "guest")
    material_id = data.get("material_id")
    if not material_id:
        return None
    material = storage.get_material(username, material_id)
    return material["text"] if material else None


if __name__ == "__main__":
    app.run(debug=True, port=5000)
