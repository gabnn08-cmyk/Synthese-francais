const app = document.querySelector("#app");

const state = {
  user: null,
  students: [],
  selectedStudentId: null,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.error || "Une erreur est survenue.");
  }
  return data;
}

function numberOrDash(value) {
  return value === null || value === undefined ? "-" : `${value.toFixed(2)}/20`;
}

function renderSummaryCard(title, items) {
  return `
    <article class="stat-card">
      <p class="eyebrow">${title}</p>
      <ul class="summary-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>
    </article>
  `;
}

function renderLogin() {
  const template = document.querySelector("#login-template");
  app.innerHTML = "";
  app.appendChild(template.content.cloneNode(true));
  const form = document.querySelector("#login-form");
  const error = document.querySelector("#login-error");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    const formData = new FormData(form);
    try {
      const data = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      state.user = data.user;
      await boot();
    } catch (err) {
      error.textContent = err.message;
    }
  });
}

function studentFormMarkup(isTeacher = false) {
  return `
    <form id="evaluation-form" class="stack">
      ${isTeacher ? `
      <label>
        Eleve concerne
        <select name="student_id" required>
          <option value="">Choisir un eleve</option>
          ${state.students.map((student) => `<option value="${student.id}">${student.full_name}</option>`).join("")}
        </select>
      </label>` : ""}
      <label>
        Intitule de l'evaluation
        <input name="title" type="text" placeholder="Commentaire compose 3" required>
      </label>
      <label>
        Type
        <select name="evaluation_type" required>
          <option value="ecrit">Ecrit</option>
          <option value="oral">Oral</option>
        </select>
      </label>
      <label>
        Domaine
        <input name="subject_area" type="text" placeholder="Analyse litteraire" required>
      </label>
      <label>
        Date
        <input name="evaluation_date" type="date" required>
      </label>
      <label>
        Note obtenue
        <input name="score" type="number" min="0" step="0.25" required>
      </label>
      <label>
        Bareme
        <input name="max_score" type="number" min="1" step="0.25" value="20" required>
      </label>
      <label>
        Appreciation de la professeure
        <textarea name="appreciation" placeholder="Bonne analyse, mais il faut approfondir les justifications..." required></textarea>
      </label>
      <button type="submit" class="primary-button">Ajouter l'evaluation</button>
      <p id="form-message" class="message"></p>
    </form>
  `;
}

async function attachEvaluationForm({ isTeacher = false, onSuccess }) {
  const form = document.querySelector("#evaluation-form");
  const message = document.querySelector("#form-message");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    message.className = "message";
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      await api("/api/evaluations", { method: "POST", body: JSON.stringify(payload) });
      message.textContent = "Evaluation enregistree.";
      message.classList.add("success");
      form.reset();
      if (!isTeacher) {
        form.querySelector("input[name='max_score']").value = "20";
      }
      await onSuccess();
    } catch (err) {
      message.textContent = err.message;
      message.classList.add("error");
    }
  });
}

function evaluationsTable(evaluations) {
  if (!evaluations.length) {
    return `<p class="empty-state">Aucune evaluation saisie pour le moment.</p>`;
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Evaluation</th>
            <th>Type</th>
            <th>Note</th>
            <th>Appreciation</th>
          </tr>
        </thead>
        <tbody>
          ${evaluations.map((evaluation) => `
            <tr>
              <td>${evaluation.evaluation_date}</td>
              <td><strong>${evaluation.title}</strong><br><span class="muted">${evaluation.subject_area}</span></td>
              <td><span class="badge">${evaluation.evaluation_type}</span></td>
              <td>${evaluation.score}/${evaluation.max_score}</td>
              <td>${evaluation.appreciation}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function renderStudentDashboard() {
  const [{ evaluations }, { summary }, { summary: classSummary }] = await Promise.all([
    api("/api/evaluations"),
    api(`/api/student-summary/${state.user.id}`),
    api("/api/class-summary"),
  ]);

  app.innerHTML = `
    <section class="dashboard">
      <div class="panel">
        <div class="toolbar">
          <div>
            <p class="eyebrow">Espace eleve</p>
            <h2>${state.user.full_name}</h2>
            <p class="muted">Saisie personnelle des notes et appreciations de francais.</p>
          </div>
          <button id="logout-button" class="ghost-button">Deconnexion</button>
        </div>
      </div>
      <section class="stats-grid">
        <article class="stat-card"><p class="stat-label">Moyenne generale</p><p class="stat-value">${numberOrDash(summary.stats.average)}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne ecrite</p><p class="stat-value">${numberOrDash(summary.stats.written_average)}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne orale</p><p class="stat-value">${numberOrDash(summary.stats.oral_average)}</p></article>
        <article class="stat-card"><p class="stat-label">Evaluations saisies</p><p class="stat-value">${summary.stats.evaluations_count}</p></article>
      </section>
      <section class="summary-grid">
        ${renderSummaryCard("Forces", summary.strengths)}
        ${renderSummaryCard("Faiblesses", summary.weaknesses)}
        ${renderSummaryCard("Voies d'amelioration", summary.improvements)}
      </section>
      <section class="panel">
        <p class="eyebrow">Avis general</p>
        <h3>${summary.general_opinion}</h3>
      </section>
      <section class="panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Vue d'ensemble</p>
            <h3>Synthese generale de la classe</h3>
          </div>
          <span class="badge">${classSummary.students_count} eleves</span>
        </div>
        <section class="stats-grid">
          <article class="stat-card"><p class="stat-label">Moyenne de classe</p><p class="stat-value">${classSummary.class_average === null ? "-" : `${classSummary.class_average.toFixed(2)}/20`}</p></article>
          <article class="stat-card"><p class="stat-label">Evaluations recensees</p><p class="stat-value">${classSummary.evaluations_count}</p></article>
        </section>
        <section class="summary-grid">
          ${renderSummaryCard("Forces recurrentes", classSummary.top_strengths)}
          ${renderSummaryCard("Axes d'amelioration recurrents", classSummary.top_improvements)}
        </section>
        <section class="stat-card">
          <p class="eyebrow">Avis general sur la classe</p>
          <h3>${classSummary.general_opinion}</h3>
        </section>
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">Nouvelle evaluation</p><h3>Ajouter un ecrit ou un oral</h3></div></div>
        ${studentFormMarkup(false)}
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">Historique</p><h3>Mes evaluations</h3></div></div>
        ${evaluationsTable(evaluations)}
      </section>
    </section>
  `;
  document.querySelector("#logout-button").addEventListener("click", logout);
  await attachEvaluationForm({ onSuccess: renderStudentDashboard });
}

function teacherStudentButtons() {
  return state.students.map((student) => `
    <button class="student-button ${state.selectedStudentId === student.id ? "active" : ""}" data-student-id="${student.id}">
      <strong>${student.full_name}</strong><br>
      <span class="muted">${student.username}</span>
    </button>
  `).join("");
}

async function renderTeacherDashboard() {
  const [{ students }, { summary }] = await Promise.all([
    api("/api/students"),
    api("/api/class-summary"),
  ]);
  state.students = students;
  state.selectedStudentId = state.selectedStudentId || students[0]?.id || null;

  let selectedSummary = null;
  let selectedEvaluations = [];
  if (state.selectedStudentId) {
    const [studentSummaryData, evaluationsData] = await Promise.all([
      api(`/api/student-summary/${state.selectedStudentId}`),
      api(`/api/evaluations?student_id=${state.selectedStudentId}`),
    ]);
    selectedSummary = studentSummaryData.summary;
    selectedEvaluations = evaluationsData.evaluations;
  }

  app.innerHTML = `
    <section class="dashboard">
      <div class="panel">
        <div class="toolbar">
          <div>
            <p class="eyebrow">Espace professeure</p>
            <h2>${state.user.full_name}</h2>
            <p class="muted">Vue globale de la classe et lecture des syntheses individuelles.</p>
          </div>
          <button id="logout-button" class="ghost-button">Deconnexion</button>
        </div>
      </div>
      <section class="stats-grid">
        <article class="stat-card"><p class="stat-label">Eleves suivis</p><p class="stat-value">${summary.students_count}</p></article>
        <article class="stat-card"><p class="stat-label">Evaluations totales</p><p class="stat-value">${summary.evaluations_count}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne de classe</p><p class="stat-value">${summary.class_average === null ? "-" : `${summary.class_average.toFixed(2)}/20`}</p></article>
      </section>
      <section class="summary-grid">
        ${renderSummaryCard("Forces recurrentes", summary.top_strengths)}
        ${renderSummaryCard("Axes d'amelioration recurrents", summary.top_improvements)}
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">Ajout rapide</p><h3>Saisir une evaluation pour un eleve</h3></div></div>
        ${studentFormMarkup(true)}
      </section>
      <section class="teacher-grid">
        <aside class="panel">
          <p class="eyebrow">Classe</p>
          <h3>Syntheses individuelles</h3>
          <div class="student-list">${teacherStudentButtons()}</div>
        </aside>
        <section class="panel">
          ${selectedSummary ? `
            <div class="student-head">
              <div><p class="eyebrow">Eleve selectionne</p><h3>${selectedSummary.student.full_name}</h3></div>
              <span class="badge">${selectedSummary.stats.evaluations_count} evaluations</span>
            </div>
            <section class="stats-grid">
              <article class="stat-card"><p class="stat-label">Moyenne generale</p><p class="stat-value">${numberOrDash(selectedSummary.stats.average)}</p></article>
              <article class="stat-card"><p class="stat-label">Ecrit</p><p class="stat-value">${numberOrDash(selectedSummary.stats.written_average)}</p></article>
              <article class="stat-card"><p class="stat-label">Oral</p><p class="stat-value">${numberOrDash(selectedSummary.stats.oral_average)}</p></article>
            </section>
            <section class="summary-grid">
              ${renderSummaryCard("Forces", selectedSummary.strengths)}
              ${renderSummaryCard("Faiblesses", selectedSummary.weaknesses)}
              ${renderSummaryCard("Voies d'amelioration", selectedSummary.improvements)}
            </section>
            <section class="stat-card">
              <p class="eyebrow">Avis general</p>
              <h3>${selectedSummary.general_opinion}</h3>
            </section>
            <section class="panel" style="padding:0;box-shadow:none;border:0;background:transparent;">
              <div class="panel-header"><div><p class="eyebrow">Historique</p><h3>Evaluations enregistrees</h3></div></div>
              ${evaluationsTable(selectedEvaluations)}
            </section>
          ` : `<p class="empty-state">Aucun eleve disponible.</p>`}
        </section>
      </section>
    </section>
  `;

  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelectorAll("[data-student-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStudentId = Number(button.dataset.studentId);
      renderTeacherDashboard();
    });
  });
  await attachEvaluationForm({ isTeacher: true, onSuccess: renderTeacherDashboard });
}

async function logout() {
  await api("/api/logout", { method: "POST", body: "{}" });
  state.user = null;
  state.selectedStudentId = null;
  renderLogin();
}

async function boot() {
  try {
    const session = await api("/api/session");
    state.user = session.authenticated ? session.user : null;
    if (!state.user) {
      renderLogin();
      return;
    }
    if (state.user.role === "teacher") {
      await renderTeacherDashboard();
      return;
    }
    await renderStudentDashboard();
  } catch {
    renderLogin();
  }
}

boot();
