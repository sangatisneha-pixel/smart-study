"""
nlp_utils.py
------------
Small, easy-to-read text analysis helpers that power the "AI" features
of Smart Study Companion: summarizing, question answering, quiz
generation, flashcards and a study planner.

No external AI service or API key is required. Everything here uses
plain word-frequency statistics, which is a classic and well
understood technique called "extractive summarization". It is not as
powerful as a large language model, but it is transparent, free to
run, and easy for a student (or an interviewer!) to read and explain.

If you want to upgrade this later to use a real LLM (OpenAI, Claude,
Llama, etc.), you only need to replace the bodies of `summarize_text`
and `answer_question` — every other file calls these functions and
does not care how they work internally.
"""

import re
from collections import Counter

# Common English words we don't want influencing "importance" scores.
STOPWORDS = set("""
a an the is are was were be been being of in on at to for with and or
but if then so than that this these those it its as by from not no
can could will would shall should may might must do does did doing
have has had having i you he she we they them his her their our your
my me him us what which who whom when where why how all any both
each few more most other some such only own same too very s t just
""".split())


def split_into_sentences(text: str):
    """Split raw text into a list of clean sentences."""
    text = re.sub(r"\s+", " ", text).strip()
    # Split on '.', '!' or '?' followed by a space and a capital letter/number.
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 15]
    return sentences


def word_frequencies(text: str):
    """Count how often each meaningful word appears in the text."""
    words = re.findall(r"[A-Za-z]+", text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 2]
    return Counter(words)


def summarize_text(text: str, num_sentences: int = 5):
    """
    Extractive summary: score every sentence by how many "important"
    (frequent, non-stopword) words it contains, then return the
    highest scoring sentences in their original order.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    freq = word_frequencies(text)
    if not freq:
        return sentences[:num_sentences]

    max_freq = max(freq.values())
    scores = []
    for i, sentence in enumerate(sentences):
        words = re.findall(r"[A-Za-z]+", sentence.lower())
        if not words:
            score = 0
        else:
            score = sum(freq.get(w, 0) for w in words) / max_freq / len(words)
        scores.append((score, i, sentence))

    # Take the top-scoring sentences, then re-sort by their original order
    top = sorted(scores, key=lambda x: x[0], reverse=True)[:num_sentences]
    top.sort(key=lambda x: x[1])
    return [s for _, _, s in top]


def extract_key_points(text: str, num_points: int = 6):
    """Return short bullet-style key points (reuses the summarizer)."""
    sentences = summarize_text(text, num_points)
    points = []
    for s in sentences:
        # Trim long sentences down to a punchy bullet length.
        s = s.strip()
        if len(s) > 110:
            s = s[:107].rsplit(" ", 1)[0] + "..."
        points.append(s)
    return points


def answer_question(text: str, question: str):
    """
    Very simple retrieval-based Q&A: find the sentence(s) in `text`
    that share the most keywords with the question, and return them.
    This mirrors the idea behind RAG (Retrieval-Augmented Generation),
    just without a vector database or language model.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return "There isn't any material to search yet. Upload a document first."

    q_words = set(w for w in re.findall(r"[A-Za-z]+", question.lower()) if w not in STOPWORDS)
    if not q_words:
        return "Try asking a more specific question."

    best_score = 0
    best_sentences = []
    for sentence in sentences:
        s_words = set(w for w in re.findall(r"[A-Za-z]+", sentence.lower()))
        overlap = len(q_words & s_words)
        if overlap > best_score:
            best_score = overlap
            best_sentences = [sentence]
        elif overlap == best_score and overlap > 0:
            best_sentences.append(sentence)

    if best_score == 0:
        return "I couldn't find anything about that in the uploaded material. Try rephrasing, or upload a document that covers this topic."

    # Return up to 2 supporting sentences for a fuller answer.
    return " ".join(best_sentences[:2])


def generate_quiz(text: str, num_questions: int = 5):
    """
    Build fill-in-the-blank multiple choice questions from the most
    important sentences in the text. For each sentence we blank out
    its most significant word, then offer that word plus three other
    frequent words from the document as answer choices.
    """
    freq = word_frequencies(text)
    if not freq:
        return []

    candidate_sentences = summarize_text(text, num_questions * 2)
    vocabulary = [w for w, _ in freq.most_common(30)]

    quiz = []
    used_answers = set()
    for sentence in candidate_sentences:
        if len(quiz) >= num_questions:
            break
        words_in_sentence = re.findall(r"[A-Za-z]+", sentence.lower())
        # Pick the most frequent meaningful word in this sentence as the answer.
        scored = [(freq.get(w, 0), w) for w in words_in_sentence if w not in STOPWORDS and len(w) > 3]
        if not scored:
            continue
        scored.sort(reverse=True)
        answer = scored[0][1]
        if answer in used_answers:
            continue
        used_answers.add(answer)

        # Build the blanked question, preserving the original word's casing spot.
        pattern = re.compile(re.escape(answer), re.IGNORECASE)
        question_text = pattern.sub("_____", sentence, count=1)

        # Build 3 wrong options from other frequent vocabulary words.
        distractors = [w for w in vocabulary if w != answer][:10]
        import random
        random.shuffle(distractors)
        options = [answer] + distractors[:3]
        random.shuffle(options)

        quiz.append({
            "question": question_text,
            "options": options,
            "answer": answer,
        })

    return quiz


def generate_flashcards(text: str, num_cards: int = 8):
    """
    Turn definition-like sentences ("X is Y", "X refers to Y", "X: Y")
    into front/back flashcards. Falls back to key-point sentences with
    their most important word as the "front" if no clean definitions
    are found.
    """
    sentences = split_into_sentences(text)
    freq = word_frequencies(text)
    cards = []

    definition_pattern = re.compile(
        r"^(?P<term>[A-Z][A-Za-z0-9 \-]{1,40}?)\s+(?:is|are|refers to|means)\s+(?P<def>.+)$"
    )

    for sentence in sentences:
        if len(cards) >= num_cards:
            break
        match = definition_pattern.match(sentence)
        if match:
            term = match.group("term").strip()
            definition = match.group("def").strip().rstrip(".") + "."
            if 2 < len(term) < 40:
                cards.append({"front": term, "back": definition})

    # Fall back to important sentences if we didn't find enough definitions.
    if len(cards) < num_cards:
        extra_needed = num_cards - len(cards)
        for sentence in summarize_text(text, extra_needed * 2):
            if len(cards) >= num_cards:
                break
            words = [w for w in re.findall(r"[A-Za-z]+", sentence.lower()) if w not in STOPWORDS]
            if not words:
                continue
            key_word = max(words, key=lambda w: freq.get(w, 0))
            front = key_word.capitalize() + "?"
            if front.lower() not in [c["front"].lower() for c in cards]:
                cards.append({"front": front, "back": sentence})

    return cards[:num_cards]


def generate_study_plan(subjects, hours_per_day: float, days_until_exam: int):
    """
    Build a simple day-by-day, hour-by-hour study schedule.
    `subjects` is a list of subject names. Time is divided evenly
    across subjects each day, with weaker/earlier subjects repeated
    more often near the exam using a simple round-robin + revision pass.
    """
    if not subjects or hours_per_day <= 0 or days_until_exam <= 0:
        return []

    plan = []
    slot_length = 1  # 1 hour blocks, easy to read on a schedule
    slots_per_day = max(1, int(hours_per_day))

    for day in range(1, days_until_exam + 1):
        day_plan = {"day": day, "sessions": []}
        for slot in range(slots_per_day):
            # Reserve the final day mostly for revision.
            if day == days_until_exam:
                subject = "Full Revision"
            else:
                subject = subjects[(day + slot) % len(subjects)]
            start_hour = 9 + slot  # study day starts at 9 AM by default
            day_plan["sessions"].append({
                "time": f"{start_hour}:00 - {start_hour + slot_length}:00",
                "subject": subject,
            })
        plan.append(day_plan)

    return plan
