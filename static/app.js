const app = document.querySelector("#app");

const state = {
  user: null,
  students: [],
  selectedStudentId: null,
  editingEvaluationId: null,
};

const STAFF_ROLES = new Set(["admin", "teacher"]);

function isStaff(user = state.user) {
  return STAFF_ROLES.has(user?.role);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

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

function renderTrimesterAverages(trimesterAverages = {}) {
  return `
    <section class="stats-grid">
      ${[1, 2, 3].map((trimester) => `
        <article class="stat-card">
          <p class="stat-label">Moyenne T${trimester}</p>
          <p class="stat-value">${numberOrDash(trimesterAverages[String(trimester)])}</p>
        </article>
      `).join("")}
    </section>
  `;
}

function renderSummaryCard(title, items) {
  return `
    <article class="stat-card">
      <p class="eyebrow">${escapeHtml(title)}</p>
      <ul class="summary-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </article>
  `;
}

function formValue(evaluation, field, fallback = "") {
  return escapeHtml(evaluation?.[field] ?? fallback);
}

function selectedAttr(evaluation, field, value, fallback = "") {
  const current = String(evaluation?.[field] ?? fallback);
  return current === String(value) ? " selected" : "";
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
  const registerForm = document.querySelector("#register-form");
  if (registerForm) {
    const registerError = document.querySelector("#register-error");
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      registerError.textContent = "";
      const formData = new FormData(registerForm);
      try {
        const data = await api("/api/register", {
          method: "POST",
          body: JSON.stringify({
            full_name: formData.get("full_name"),
            username: formData.get("username"),
            password: formData.get("password"),
          }),
        });
        state.user = data.user;
        await boot();
      } catch (err) {
        registerError.textContent = err.message;
      }
    });
  }
}

function studentFormMarkup(isTeacher = false, evaluation = null) {
  const isEditing = Boolean(evaluation);
  return `
    <form id="evaluation-form" class="stack">
      ${isTeacher ? `
      <label>
        Élève concerné
        <select name="student_id" required>
          <option value="">Choisir un élève</option>
          ${state.students.map((student) => `<option value="${student.id}">${escapeHtml(student.full_name)}</option>`).join("")}
        </select>
      </label>` : ""}
      <label>
        Intitulé de l'évaluation
        <input name="title" type="text" placeholder="Commentaire composé 3" value="${formValue(evaluation, "title")}" required>
      </label>
      <label>
        Type
        <select name="evaluation_type" required>
          <option value="ecrit"${selectedAttr(evaluation, "evaluation_type", "ecrit", "ecrit")}>Écrit</option>
          <option value="oral"${selectedAttr(evaluation, "evaluation_type", "oral")}>Oral</option>
        </select>
      </label>
      <label>
        Trimestre
        <select name="trimester" required>
          <option value="1"${selectedAttr(evaluation, "trimester", "1", "1")}>Trimestre 1</option>
          <option value="2"${selectedAttr(evaluation, "trimester", "2")}>Trimestre 2</option>
          <option value="3"${selectedAttr(evaluation, "trimester", "3")}>Trimestre 3</option>
        </select>
      </label>
      <label>
        Domaine
        <input name="subject_area" type="text" placeholder="Analyse littéraire" value="${formValue(evaluation, "subject_area")}" required>
      </label>
      <label>
        Date
        <input name="evaluation_date" type="date" value="${formValue(evaluation, "evaluation_date")}" required>
      </label>
      <label>
        Note obtenue
        <input name="score" type="number" min="0" step="0.25" value="${formValue(evaluation, "score")}" required>
      </label>
      <label>
        Barème
        <input name="max_score" type="number" min="1" step="0.25" value="${formValue(evaluation, "max_score", "20")}" required>
      </label>
      <label>
        Appréciation de la professeure
        <textarea name="appreciation" placeholder="Bonne analyse, mais il faut approfondir les justifications..." required>${formValue(evaluation, "appreciation")}</textarea>
      </label>
      <div class="form-actions">
        <button type="submit" class="primary-button">${isEditing ? "Enregistrer les modifications" : "Ajouter l'évaluation"}</button>
        ${isEditing ? `<button type="button" id="cancel-edit-button" class="ghost-button">Annuler</button>` : ""}
      </div>
      <p id="form-message" class="message" aria-live="polite"></p>
    </form>
  `;
}

async function attachEvaluationForm({ isTeacher = false, editingEvaluation = null, onSuccess }) {
  const form = document.querySelector("#evaluation-form");
  const message = document.querySelector("#form-message");
  document.querySelector("#cancel-edit-button")?.addEventListener("click", async () => {
    state.editingEvaluationId = null;
    await onSuccess();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    message.className = "message";
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      if (editingEvaluation) {
        await api(`/api/evaluations/${editingEvaluation.id}`, { method: "PUT", body: JSON.stringify(payload) });
        state.editingEvaluationId = null;
      } else {
        await api("/api/evaluations", { method: "POST", body: JSON.stringify(payload) });
      }
      message.textContent = editingEvaluation ? "Évaluation modifiée." : "Évaluation enregistrée.";
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

function evaluationsTable(evaluations, { canManage = false } = {}) {
  if (!evaluations.length) {
    return `<p class="empty-state">Aucune évaluation saisie pour le moment.</p>`;
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Évaluation</th>
            <th>Type</th>
            <th>Trimestre</th>
            <th>Note</th>
            <th>Appréciation</th>
            ${canManage ? "<th>Actions</th>" : ""}
          </tr>
        </thead>
        <tbody>
          ${evaluations.map((evaluation) => `
            <tr>
              <td data-label="Date">${escapeHtml(evaluation.evaluation_date)}</td>
              <td data-label="Evaluation"><strong>${escapeHtml(evaluation.title)}</strong><br><span class="muted">${escapeHtml(evaluation.subject_area)}</span></td>
              <td data-label="Type"><span class="badge">${escapeHtml(evaluation.evaluation_type)}</span></td>
              <td data-label="Trimestre"><span class="badge">T${escapeHtml(evaluation.trimester || 1)}</span></td>
              <td data-label="Note">${escapeHtml(evaluation.score)}/${escapeHtml(evaluation.max_score)}</td>
              <td data-label="Appreciation">${escapeHtml(evaluation.appreciation)}</td>
              ${canManage ? `
              <td data-label="Actions">
                <div class="row-actions">
                  <button type="button" class="small-button" data-edit-evaluation-id="${escapeHtml(evaluation.id)}">Modifier</button>
                  <button type="button" class="small-button danger-button" data-delete-evaluation-id="${escapeHtml(evaluation.id)}">Supprimer</button>
                </div>
              </td>` : ""}
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function attachEvaluationActions(evaluations, refresh) {
  document.querySelectorAll("[data-edit-evaluation-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.editingEvaluationId = Number(button.dataset.editEvaluationId);
      await refresh();
      document.querySelector("#evaluation-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.querySelectorAll("[data-delete-evaluation-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const evaluationId = Number(button.dataset.deleteEvaluationId);
      const evaluation = evaluations.find((item) => item.id === evaluationId);
      if (!window.confirm(`Supprimer l'évaluation "${evaluation?.title || ""}" ?`)) {
        return;
      }
      await api(`/api/evaluations/${evaluationId}`, { method: "DELETE" });
      if (state.editingEvaluationId === evaluationId) {
        state.editingEvaluationId = null;
      }
      await refresh();
    });
  });
}

async function renderStudentDashboard() {
  const [{ evaluations }, { summary }, { summary: classSummary }] = await Promise.all([
    api("/api/evaluations"),
    api(`/api/student-summary/${state.user.id}`),
    api("/api/class-summary"),
  ]);
  const editingEvaluation = evaluations.find((evaluation) => evaluation.id === state.editingEvaluationId) || null;

  app.innerHTML = `
    <section class="dashboard">
      <div class="panel">
        <div class="toolbar">
          <div>
            <p class="eyebrow">Espace élève</p>
            <h2>${escapeHtml(state.user.full_name)}</h2>
            <p class="muted">Saisie personnelle des notes et appréciations de français.</p>
          </div>
          <button id="logout-button" class="ghost-button">Deconnexion</button>
        </div>
      </div>
      <section class="stats-grid">
        <article class="stat-card"><p class="stat-label">Moyenne générale</p><p class="stat-value">${numberOrDash(summary.stats.average)}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne écrite</p><p class="stat-value">${numberOrDash(summary.stats.written_average)}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne orale</p><p class="stat-value">${numberOrDash(summary.stats.oral_average)}</p></article>
        <article class="stat-card"><p class="stat-label">Évaluations saisies</p><p class="stat-value">${summary.stats.evaluations_count}</p></article>
      </section>
      ${renderTrimesterAverages(summary.stats.trimester_averages)}
      <section class="summary-grid">
        ${renderSummaryCard("Forces", summary.strengths)}
        ${renderSummaryCard("Points de vigilance", summary.weaknesses)}
        ${renderSummaryCard("Conseils concrets", summary.improvements)}
      </section>
      <section class="panel">
        <p class="eyebrow">Avis général</p>
        <h3>${escapeHtml(summary.general_opinion)}</h3>
      </section>
      <section class="panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Vue d'ensemble</p>
            <h3>Synthèse générale de la classe</h3>
          </div>
          <span class="badge">${escapeHtml(classSummary.students_count)} élèves</span>
        </div>
        <section class="stats-grid">
          <article class="stat-card"><p class="stat-label">Moyenne de classe</p><p class="stat-value">${classSummary.class_average === null ? "-" : `${classSummary.class_average.toFixed(2)}/20`}</p></article>
          <article class="stat-card"><p class="stat-label">Évaluations recensées</p><p class="stat-value">${classSummary.evaluations_count}</p></article>
        </section>
        ${renderTrimesterAverages(classSummary.trimester_averages)}
        <section class="summary-grid">
          ${renderSummaryCard("Forces récurrentes", classSummary.top_strengths)}
          ${renderSummaryCard("Conseils récurrents", classSummary.top_improvements)}
        </section>
        <section class="stat-card">
          <p class="eyebrow">Avis général sur la classe</p>
          <h3>${escapeHtml(classSummary.general_opinion)}</h3>
        </section>
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">${editingEvaluation ? "Modification" : "Nouvelle évaluation"}</p><h3>${editingEvaluation ? "Corriger une évaluation" : "Ajouter un écrit ou un oral"}</h3></div></div>
        ${studentFormMarkup(false, editingEvaluation)}
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">Historique</p><h3>Mes évaluations</h3></div></div>
        ${evaluationsTable(evaluations, { canManage: true })}
      </section>
    </section>
  `;
  document.querySelector("#logout-button").addEventListener("click", logout);
  await attachEvaluationForm({ editingEvaluation, onSuccess: renderStudentDashboard });
  attachEvaluationActions(evaluations, renderStudentDashboard);
}

function teacherStudentButtons() {
  return state.students.map((student) => `
    <button class="student-button ${state.selectedStudentId === student.id ? "active" : ""}" data-student-id="${student.id}">
      <strong>${escapeHtml(student.full_name)}</strong><br>
      <span class="muted">${escapeHtml(student.username)}</span>
    </button>
  `).join("");
}

async function renderStaffDashboard() {
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
            <p class="eyebrow">${state.user.role === "admin" ? "Espace administration" : "Espace professeure"}</p>
            <h2>${escapeHtml(state.user.full_name)}</h2>
            <p class="muted">Vue globale de la classe et lecture des synthèses individuelles.</p>
          </div>
          <button id="logout-button" class="ghost-button">Deconnexion</button>
        </div>
      </div>
      <section class="stats-grid">
        <article class="stat-card"><p class="stat-label">Élèves suivis</p><p class="stat-value">${summary.students_count}</p></article>
        <article class="stat-card"><p class="stat-label">Évaluations totales</p><p class="stat-value">${summary.evaluations_count}</p></article>
        <article class="stat-card"><p class="stat-label">Moyenne de classe</p><p class="stat-value">${summary.class_average === null ? "-" : `${summary.class_average.toFixed(2)}/20`}</p></article>
      </section>
      ${renderTrimesterAverages(summary.trimester_averages)}
      <section class="summary-grid">
        ${renderSummaryCard("Forces récurrentes", summary.top_strengths)}
        ${renderSummaryCard("Conseils récurrents", summary.top_improvements)}
      </section>
      <section class="panel">
        <div class="panel-header"><div><p class="eyebrow">Ajout rapide</p><h3>Saisir une évaluation pour un élève</h3></div></div>
        ${studentFormMarkup(true)}
      </section>
      <section class="teacher-grid">
        <aside class="panel">
          <p class="eyebrow">Classe</p>
          <h3>Synthèses individuelles</h3>
          <div class="student-list">${teacherStudentButtons()}</div>
        </aside>
        <section class="panel">
          ${selectedSummary ? `
            <div class="student-head">
              <div><p class="eyebrow">Élève sélectionné</p><h3>${escapeHtml(selectedSummary.student.full_name)}</h3></div>
              <span class="badge">${escapeHtml(selectedSummary.stats.evaluations_count)} évaluations</span>
            </div>
            <section class="stats-grid">
              <article class="stat-card"><p class="stat-label">Moyenne générale</p><p class="stat-value">${numberOrDash(selectedSummary.stats.average)}</p></article>
              <article class="stat-card"><p class="stat-label">Écrit</p><p class="stat-value">${numberOrDash(selectedSummary.stats.written_average)}</p></article>
              <article class="stat-card"><p class="stat-label">Oral</p><p class="stat-value">${numberOrDash(selectedSummary.stats.oral_average)}</p></article>
            </section>
            ${renderTrimesterAverages(selectedSummary.stats.trimester_averages)}
            <section class="summary-grid">
              ${renderSummaryCard("Forces", selectedSummary.strengths)}
              ${renderSummaryCard("Points de vigilance", selectedSummary.weaknesses)}
              ${renderSummaryCard("Conseils concrets", selectedSummary.improvements)}
            </section>
            <section class="stat-card">
              <p class="eyebrow">Avis général</p>
              <h3>${escapeHtml(selectedSummary.general_opinion)}</h3>
            </section>
            <section class="panel" style="padding:0;box-shadow:none;border:0;background:transparent;">
              <div class="panel-header"><div><p class="eyebrow">Historique</p><h3>Évaluations enregistrées</h3></div></div>
              ${evaluationsTable(selectedEvaluations)}
            </section>
          ` : `<p class="empty-state">Aucun élève disponible.</p>`}
        </section>
      </section>
    </section>
  `;

  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelectorAll("[data-student-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStudentId = Number(button.dataset.studentId);
      renderStaffDashboard();
    });
  });
  await attachEvaluationForm({ isTeacher: true, onSuccess: renderStaffDashboard });
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
    if (isStaff()) {
      await renderStaffDashboard();
      return;
    }
    await renderStudentDashboard();
  } catch {
    renderLogin();
  }
}

boot();
