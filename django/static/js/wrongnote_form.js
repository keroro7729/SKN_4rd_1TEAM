(() => {
  const root = document.querySelector("[data-submission-id]");
  if (!root) return;

  const tabs = Array.from(document.querySelectorAll(".reflection-tab"));
  const panels = Array.from(document.querySelectorAll(".reflection-panel"));
  const saveBtn = document.getElementById("wrongnote-save-btn");
  const statusText = document.getElementById("wrongnote-status");
  const commentInput = document.getElementById("wrongnote-comment");
  const countText = document.getElementById("comment-count");
  const savedReflection = document.getElementById("saved-reflection");
  const feedbackResult = document.getElementById("feedback-result");
  const similarBox = document.getElementById("similar-notes");
  const similarEmpty = document.getElementById("similar-empty");
  const analysisBox = document.getElementById("ai-analysis");
  const analysisEmpty = document.getElementById("analysis-empty");
  const historyView = document.getElementById("history-code-view");

  const getCookie = (name) => {
    const found = (document.cookie || "")
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(`${name}=`));
    return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
  };

  const escapeHtml = (value) => String(value || "").replace(/[&<>\"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const activateTab = (targetName) => {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === targetName));
    panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === targetName));
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });

  const updateCount = () => {
    if (countText && commentInput) countText.textContent = String(commentInput.value.length);
  };

  commentInput?.addEventListener("input", updateCount);
  updateCount();

  document.querySelectorAll(".template-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const text = btn.dataset.template || "";
      commentInput.value = commentInput.value ? `${commentInput.value}\n${text}` : text;
      commentInput.focus();
      updateCount();
    });
  });

  document.querySelectorAll(".copy-code-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      try {
        await navigator.clipboard?.writeText(target.textContent || "");
        btn.textContent = "복사됨";
      } catch (_) {
        btn.textContent = "복사 실패";
      }
      setTimeout(() => { btn.textContent = "복사"; }, 1000);
    });
  });

  document.querySelectorAll(".history-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".history-item").forEach((item) => item.classList.remove("is-active"));
      btn.classList.add("is-active");
      const template = document.getElementById(btn.dataset.codeTemplate);
      historyView.textContent = template ? template.textContent.trim() : "코드가 없습니다.";
    });
  });

  const renderSimilar = (similarNotes = []) => {
    if (!similarBox || !similarEmpty) return;
    if (!similarNotes.length) {
      similarEmpty.textContent = "유사 오답노트가 없습니다.";
      similarEmpty.hidden = false;
      similarBox.hidden = true;
      return;
    }
    similarBox.innerHTML = similarNotes.map((note) => `
      <article class="evidence-card">
        <strong>note_id ${escapeHtml(note.note_id || "-")}</strong>
        <span>source ${escapeHtml(note.source || "wrong_notes")}</span>
        <span>score ${escapeHtml(note.score || "-")}</span>
      </article>
    `).join("");
    similarBox.hidden = false;
    similarEmpty.hidden = true;
  };

  const renderAnalysis = (analysis = {}, errors = []) => {
    if (!analysisBox || !analysisEmpty) return;
    const rows = [
      ["문제 핵심", analysis.problem_core],
      ["오답 원인", analysis.cause],
      ["풀이 과정", analysis.solution],
      ["주의사항", analysis.caution],
    ];
    analysisBox.innerHTML = rows.map(([title, body]) => `
      <article class="analysis-card">
        <strong>${title}</strong>
        <p>${escapeHtml(body || "아직 분석 결과가 없습니다.")}</p>
      </article>
    `).join("");
    if (errors.length) {
      analysisBox.innerHTML += `<pre class="result-pre result-error-text">${escapeHtml(errors.map((error) => `${error.stage}: ${error.message}`).join("\n"))}</pre>`;
    }
    analysisBox.hidden = false;
    analysisEmpty.hidden = true;
  };

  saveBtn?.addEventListener("click", async () => {
    const comment = (commentInput?.value || "").trim();
    if (!comment) {
      statusText.textContent = "회고를 먼저 작성하세요.";
      commentInput?.focus();
      return;
    }

    saveBtn.disabled = true;
    statusText.textContent = "저장 및 AI 분석 요청 중입니다.";
    feedbackResult.hidden = false;
    savedReflection.textContent = comment;
    renderSimilar([]);
    analysisBox.hidden = true;
    analysisEmpty.hidden = false;
    analysisEmpty.textContent = "AI 분석 결과를 기다리는 중입니다.";

    try {
      const response = await fetch(window.location.pathname, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
        },
        body: JSON.stringify({
          submission_id: Number(root.dataset.submissionId),
          problem_id: Number(root.dataset.problemId),
          comment,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error_message || "오답노트 저장에 실패했습니다.");
      const ai = data.ai_analysis || {};
      renderSimilar(ai.similar_notes || []);
      renderAnalysis(ai.analysis || {}, ai.errors || []);
      statusText.textContent = `저장 완료 · note_id ${data.wrong_note_id} · ${data.status}`;
      feedbackResult.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      statusText.textContent = error.message;
      analysisEmpty.textContent = "AI 분석을 불러오지 못했습니다.";
    } finally {
      saveBtn.disabled = false;
    }
  });
})();
