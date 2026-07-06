(() => {
  const page = document.querySelector("[data-submission-id]");
  if (!page) return;

  const inputStep = document.getElementById("wn-step-input");
  const feedbackStep = document.getElementById("wn-step-feedback");
  const stepButtons = document.querySelectorAll(".wn-flow-step");
  const commentInput = document.getElementById("wrongnote-comment");
  const saveButton = document.getElementById("wrongnote-save-btn");
  const rewriteButton = document.getElementById("wrongnote-rewrite-btn");
  const statusText = document.getElementById("wrongnote-status");
  const similarBox = document.getElementById("similar-notes");
  const similarEmpty = document.getElementById("similar-empty");
  const analysisBox = document.getElementById("ai-analysis");
  const analysisEmpty = document.getElementById("analysis-empty");
  const countText = document.getElementById("comment-count");
  const savedCommentPreview = document.getElementById("saved-comment-preview");
  const detailLink = document.getElementById("wrongnote-detail-link");

  const getCookie = (name) => {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const rawCookie of cookies) {
      const cookie = rawCookie.trim();
      if (cookie.startsWith(`${name}=`)) {
        return decodeURIComponent(cookie.slice(name.length + 1));
      }
    }
    return "";
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const normalizeScore = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(1, number));
  };

  const scoreLabel = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    return number.toFixed(2);
  };

  const setStatus = (message, type = "info") => {
    if (!statusText) return;
    statusText.textContent = message;
    statusText.dataset.state = type;
  };

  const showStep = (target) => {
    const isFeedback = target === "feedback";
    inputStep.hidden = isFeedback;
    feedbackStep.hidden = !isFeedback;
    inputStep.classList.toggle("is-active", !isFeedback);
    feedbackStep.classList.toggle("is-active", isFeedback);
    stepButtons.forEach((button) => {
      const active = button.dataset.stepTarget === target;
      button.classList.toggle("is-active", active);
      if (button.dataset.stepTarget === "feedback" && isFeedback) {
        button.disabled = false;
      }
    });
    page.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const renderAnalysis = (analysis = {}, errors = []) => {
    const rows = [
      { key: "problem_core", title: "문제 핵심", icon: "◎", tone: "core" },
      { key: "cause", title: "오답 원인", icon: "!", tone: "cause" },
      { key: "solution", title: "풀이 과정", icon: "</>", tone: "solution" },
      { key: "caution", title: "주의사항", icon: "△", tone: "caution" },
    ];

    analysisBox.innerHTML = rows.map((row) => `
      <article class="wn-analysis-item ${row.tone}">
        <span>${row.icon}</span>
        <div>
          <strong>${row.title}</strong>
          <p>${escapeHtml(analysis[row.key] || "분석 결과가 비어 있습니다.")}</p>
        </div>
      </article>
    `).join("");

    if (analysis.evidence || analysis.recommendation) {
      analysisBox.innerHTML += `
        <article class="wn-analysis-item evidence">
          <span>⌁</span>
          <div>
            <strong>근거 / 추천</strong>
            <p>${escapeHtml(analysis.evidence || analysis.recommendation)}</p>
          </div>
        </article>
      `;
    }

    if (errors.length) {
      analysisBox.innerHTML += `
        <article class="wn-policy-box error">
          ${escapeHtml(errors.map((error) => `${error.stage || "error"}: ${error.message || error}`).join(" · "))}
        </article>
      `;
    }

    analysisBox.hidden = false;
    analysisEmpty.hidden = true;
  };

  const renderSimilar = (similarNotes = []) => {
    if (!similarNotes.length) {
      similarEmpty.innerHTML = `
        <article class="wn-empty-state">
          <strong>유사 오답노트가 없습니다.</strong>
          <p>저장 자체는 완료되었습니다. 이후 오답노트가 쌓이면 RAG 근거가 표시됩니다.</p>
        </article>
      `;
      similarEmpty.hidden = false;
      similarBox.hidden = true;
      return;
    }

    similarBox.innerHTML = similarNotes.map((note, index) => {
      const score = normalizeScore(note.score ?? note.similarity_score ?? note.distance_score);
      const scorePercent = Math.round(score * 100);
      const lowConfidence = score < 0.35;
      const noteId = note.note_id ?? note.wrong_note_id ?? note.id ?? "-";
      const source = note.source || "wrong_notes";
      const title = note.title || note.problem_title || note.problem || `유사 오답노트 #${noteId}`;
      const summary = note.summary || note.comment || note.cause || "내 과거 오답노트와 유사한 패턴입니다.";
      return `
        <article class="wn-sim-card ${lowConfidence ? "dimmed" : ""}">
          <div class="wn-rank">${index + 1}</div>
          <div class="wn-sim-main">
            <div class="wn-sim-meta">
              <strong>note_id #${escapeHtml(noteId)}</strong>
              <span>${escapeHtml(note.created_at || note.date || "RAG")}</span>
            </div>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(summary)}</p>
            <div class="wn-score-bar"><span style="width:${scorePercent}%"></span></div>
            <div class="wn-sim-foot">
              <span>source: ${escapeHtml(source)}</span>
              <b>${lowConfidence ? `${scoreLabel(score)} · 참고용` : scoreLabel(score)}</b>
            </div>
          </div>
        </article>
      `;
    }).join("");

    similarBox.hidden = false;
    similarEmpty.hidden = true;
  };

  commentInput?.addEventListener("input", () => {
    countText.textContent = commentInput.value.length;
  });

  rewriteButton?.addEventListener("click", () => {
    showStep("input");
    commentInput.focus();
  });

  saveButton?.addEventListener("click", async () => {
    const comment = commentInput.value.trim();
    if (!comment) {
      setStatus("회고를 먼저 입력하세요.", "error");
      commentInput.focus();
      return;
    }

    saveButton.disabled = true;
    saveButton.textContent = "저장 · 분석 중...";
    setStatus("오답노트 저장 및 AI/RAG 분석 요청 중입니다.", "loading");

    try {
      const response = await fetch(window.location.pathname, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
        },
        body: JSON.stringify({
          submission_id: Number(page.dataset.submissionId),
          problem_id: Number(page.dataset.problemId),
          comment,
        }),
      });

      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error_message || "오답노트 저장에 실패했습니다.");
      }

      const ai = data.ai_analysis || {};
      savedCommentPreview.textContent = comment;
      if (data.wrong_note_id) {
        detailLink.href = `/wrongnotes/${data.wrong_note_id}/`;
        detailLink.textContent = `저장된 노트 #${data.wrong_note_id} 보기`;
      }

      showStep("feedback");
      renderSimilar(ai.similar_notes || ai.evidence || []);
      renderAnalysis(ai.analysis || {}, ai.errors || []);
      setStatus(`저장 완료 · note_id #${data.wrong_note_id} · status: ${data.status}`, "success");
    } catch (error) {
      setStatus(error.message || "요청 처리 중 오류가 발생했습니다.", "error");
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = "다음 · 결과와 AI 피드백 보기";
    }
  });
})();
