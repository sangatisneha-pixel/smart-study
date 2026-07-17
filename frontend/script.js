/*
  script.js
  ---------
  Plain vanilla JavaScript — no build step, no framework. Every function
  is short and does one thing: talk to the Flask API and update the DOM.

  If your backend runs somewhere other than localhost:5000, change API_BASE.
*/

const API_BASE = "/api";

let currentUser = null;       // logged in username
let currentMaterialId = null; // convenience cache, not required elsewhere

// ---------------------------------------------------------------- auth ----

const authForm = document.getElementById("auth-form");
const authMessage = document.getElementById("auth-message");

document.getElementById("btn-register").addEventListener("click", async () => {
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  if (!username || !password) return;

  const res = await postJSON("/register", { username, password });
  authMessage.textContent = res.message;
  authMessage.style.color = res.success ? "#2F6F62" : "#D9673F";
});

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;

  const res = await postJSON("/login", { username, password });
  authMessage.textContent = res.message;
  authMessage.style.color = res.success ? "#2F6F62" : "#D9673F";

  if (res.success) {
    currentUser = username;
    document.getElementById("current-user").textContent = username;
    document.getElementById("auth-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    initApp();
  }
});

document.getElementById("btn-logout").addEventListener("click", () => {
  currentUser = null;
  document.getElementById("app").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
});

// ------------------------------------------------------------- tab nav ----

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
});

// ------------------------------------------------------------- helpers ----

async function postJSON(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function getJSON(path) {
  const res = await fetch(API_BASE + path);
  return res.json();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// ------------------------------------------------------------ app init ----

function initApp() {
  loadLibrary();
  loadProgress();
}

// -------------------------------------------------------------- upload ----

const uploadBox = document.getElementById("upload-box");
const fileInput = document.getElementById("file-input");
const uploadMessage = document.getElementById("upload-message");

uploadBox.addEventListener("click", () => fileInput.click());
uploadBox.addEventListener("dragover", (e) => { e.preventDefault(); uploadBox.classList.add("dragover"); });
uploadBox.addEventListener("dragleave", () => uploadBox.classList.remove("dragover"));
uploadBox.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadBox.classList.remove("dragover");
  if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleUpload(fileInput.files[0]);
});

async function handleUpload(file) {
  uploadMessage.textContent = "Uploading and reading text...";
  const formData = new FormData();
  formData.append("username", currentUser);
  formData.append("file", file);

  const res = await fetch(API_BASE + "/upload", { method: "POST", body: formData });
  const data = await res.json();

  uploadMessage.textContent = data.success
    ? `Added "${data.filename}". It's ready in the tools below.`
    : data.message;

  if (data.success) loadLibrary();
}

async function loadLibrary() {
  const data = await getJSON(`/materials/${currentUser}`);
  const list = document.getElementById("library-list");
  const selects = [
    document.getElementById("summarize-material"),
    document.getElementById("ask-material"),
    document.getElementById("quiz-material"),
    document.getElementById("flash-material"),
  ];

  if (!data.materials || data.materials.length === 0) {
    list.innerHTML = '<p class="muted">No materials yet — nothing here until you upload something.</p>';
    selects.forEach((s) => (s.innerHTML = '<option value="">Upload a document first</option>'));
    document.getElementById("dash-hint").classList.remove("hidden");
    return;
  }

  document.getElementById("dash-hint").classList.add("hidden");

  list.innerHTML = "";
  data.materials.forEach((m) => {
    const item = el("div", "library-item");
    item.appendChild(el("span", "filename", m.filename));
    item.appendChild(el("span", "date", new Date(m.uploaded_at).toLocaleDateString()));
    list.appendChild(item);
  });

  selects.forEach((select) => {
    select.innerHTML = "";
    data.materials.forEach((m) => {
      const option = el("option", null, m.filename);
      option.value = m.id;
      select.appendChild(option);
    });
  });

  currentMaterialId = data.materials[data.materials.length - 1].id;
}

// ------------------------------------------------------------ summarize ----

let summaryLength = "short";
document.getElementById("summary-length").addEventListener("click", (e) => {
  const btn = e.target.closest(".seg");
  if (!btn) return;
  document.querySelectorAll("#summary-length .seg").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  summaryLength = btn.dataset.length;
});

document.getElementById("btn-summarize").addEventListener("click", async () => {
  const materialId = document.getElementById("summarize-material").value;
  if (!materialId) return;

  const data = await postJSON("/summarize", {
    username: currentUser,
    material_id: materialId,
    length: summaryLength,
  });
  if (!data.success) return;

  document.getElementById("summary-output").innerHTML = data.summary
    .map((s) => `<p>${s}</p>`)
    .join("");
  document.getElementById("summary-output").classList.remove("muted");

  const kp = document.getElementById("keypoints-output");
  kp.innerHTML = data.key_points.map((p) => `<li>${p}</li>`).join("");
  kp.classList.remove("muted");
});

// ----------------------------------------------------------------- ask ----

document.getElementById("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const materialId = document.getElementById("ask-material").value;
  const input = document.getElementById("ask-input");
  const question = input.value.trim();
  if (!materialId || !question) return;

  const thread = document.getElementById("ask-thread");
  thread.appendChild(el("div", "ask-bubble ask-q", question));
  input.value = "";

  const data = await postJSON("/ask", { username: currentUser, material_id: materialId, question });
  thread.appendChild(el("div", "ask-bubble ask-a", data.answer || data.message));
  thread.scrollTop = thread.scrollHeight;
});

// ---------------------------------------------------------------- quiz ----

document.getElementById("btn-quiz").addEventListener("click", async () => {
  const materialId = document.getElementById("quiz-material").value;
  if (!materialId) return;

  const data = await postJSON("/quiz", { username: currentUser, material_id: materialId, num_questions: 5 });
  renderQuiz(data.quiz || []);
});

function renderQuiz(questions) {
  const area = document.getElementById("quiz-area");
  area.innerHTML = "";

  if (questions.length === 0) {
    area.innerHTML = '<p class="muted">Couldn\'t build a quiz from this document — try one with more full sentences.</p>';
    return;
  }

  let score = 0;
  let answered = 0;

  questions.forEach((q, qi) => {
    const card = el("div", "quiz-question");
    card.appendChild(el("h4", null, `${qi + 1}. ${q.question}`));
    const optionsWrap = el("div", "quiz-options");

    q.options.forEach((opt) => {
      const optBtn = el("button", "quiz-option", opt);
      optBtn.addEventListener("click", () => {
        if (optBtn.dataset.locked) return;
        [...optionsWrap.children].forEach((c) => (c.dataset.locked = "true"));
        const isCorrect = opt.toLowerCase() === q.answer.toLowerCase();
        optBtn.classList.add(isCorrect ? "correct" : "incorrect");
        if (!isCorrect) {
          [...optionsWrap.children].forEach((c) => {
            if (c.textContent.toLowerCase() === q.answer.toLowerCase()) c.classList.add("correct");
          });
        } else {
          score += 1;
        }
        answered += 1;
        if (answered === questions.length) showQuizSummary(score, questions.length);
      });
      optionsWrap.appendChild(optBtn);
    });

    card.appendChild(optionsWrap);
    area.appendChild(card);
  });
}

async function showQuizSummary(score, total) {
  const area = document.getElementById("quiz-area");
  const summary = el("div", "quiz-summary", `Score: ${score} / ${total}`);
  area.appendChild(summary);

  const topic = document.getElementById("quiz-material").selectedOptions[0]?.textContent || "General";
  await postJSON("/quiz/submit", { username: currentUser, topic, score, total });
  loadProgress();
}

// ----------------------------------------------------------- flashcards ----

document.getElementById("btn-flash").addEventListener("click", async () => {
  const materialId = document.getElementById("flash-material").value;
  if (!materialId) return;

  const data = await postJSON("/flashcards", { username: currentUser, material_id: materialId, num_cards: 8 });
  renderFlashcards(data.flashcards || []);
});

function renderFlashcards(cards) {
  const deck = document.getElementById("flash-deck");
  deck.innerHTML = "";

  if (cards.length === 0) {
    deck.innerHTML = '<p class="muted">Couldn\'t find enough definitions in this document yet.</p>';
    return;
  }

  cards.forEach((c) => {
    const card = el("div", "flash-card");
    const inner = el("div", "flash-card-inner");
    const front = el("div", "flash-face flash-front", c.front);
    const back = el("div", "flash-face flash-back", c.back);
    inner.appendChild(front);
    inner.appendChild(back);
    card.appendChild(inner);
    card.addEventListener("click", () => card.classList.toggle("flipped"));
    deck.appendChild(card);
  });
}

// -------------------------------------------------------------- planner ----

document.getElementById("planner-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const subjects = document
    .getElementById("planner-subjects")
    .value.split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const hours = Number(document.getElementById("planner-hours").value);
  const days = Number(document.getElementById("planner-days").value);
  if (subjects.length === 0) return;

  const data = await postJSON("/planner", {
    subjects,
    hours_per_day: hours,
    days_until_exam: days,
  });
  renderPlan(data.plan || []);
});

function renderPlan(plan) {
  const output = document.getElementById("planner-output");
  output.innerHTML = "";
  plan.forEach((day) => {
    const dayCard = el("div", "plan-day");
    dayCard.appendChild(el("h4", null, `Day ${day.day}`));
    day.sessions.forEach((s) => {
      const row = el("div", "plan-session");
      row.appendChild(el("span", "time", s.time));
      row.appendChild(el("span", null, s.subject));
      dayCard.appendChild(row);
    });
    output.appendChild(dayCard);
  });
}

// -------------------------------------------------------------- progress ----

document.getElementById("topic-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("topic-input");
  const topic = input.value.trim();
  if (!topic) return;
  input.value = "";

  await fetch(`${API_BASE}/progress/${currentUser}/complete-topic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  loadProgress();
});

async function loadProgress() {
  const data = await getJSON(`/progress/${currentUser}`);

  document.getElementById("stat-streak").textContent = data.study_streak || 0;
  document.getElementById("stat-topics").textContent = (data.topics_completed || []).length;
  document.getElementById("stat-quizzes").textContent = (data.quiz_scores || []).length;
  document.getElementById("stat-weak").textContent = (data.weak_topics || []).length || "—";

  const quizList = document.getElementById("progress-quizzes");
  if ((data.quiz_scores || []).length === 0) {
    quizList.innerHTML = '<p class="muted">No quizzes taken yet.</p>';
  } else {
    quizList.innerHTML = data.quiz_scores
      .slice()
      .reverse()
      .map(
        (q) =>
          `<div class="quiz-history-row"><span>${q.topic}</span><span class="mono">${q.score}/${q.total}</span></div>`
      )
      .join("");
  }

  const topicsWrap = document.getElementById("progress-topics");
  topicsWrap.innerHTML = "";
  (data.topics_completed || []).forEach((t) => topicsWrap.appendChild(el("span", "chip", t)));
}
