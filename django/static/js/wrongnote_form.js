(() => {
  const root = document.querySelector("[data-submission-id]");
  if (!root) return;
  const tabs = Array.from(document.querySelectorAll(".reflection-tab"));
  const panels = Array.from(document.querySelectorAll(".reflection-panel"));
  const prevBtn = document.getElementById("prev-tab-btn");
  const nextBtn = document.getElementById("next-tab-btn");
  const saveBtn = document.getElementById("wrongnote-save-btn");
  const statusText = document.getElementById("wrongnote-status");
  const commentInput = document.getElementById("wrongnote-comment");
  const countText = document.getElementById("comment-count");
  const reflectionStage = document.getElementById("reflection-stage");
  const feedbackStage = document.getElementById("feedback-stage");
  const savedReflection = document.getElementById("saved-reflection");
  const similarBox = document.getElementById("similar-notes");
  const similarEmpty = document.getElementById("similar-empty");
  const analysisBox = document.getElementById("ai-analysis");
  const analysisEmpty = document.getElementById("analysis-empty");
  const historyView = document.getElementById("history-code-view");
  let activeIndex = 0;
  const getCookie = (name) => (document.cookie || "").split(";").map(v=>v.trim()).find(v=>v.startsWith(`${name}=`))?.slice(name.length + 1) || "";
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const activate = (index) => { activeIndex = Math.max(0, Math.min(tabs.length - 1, index)); tabs.forEach((tab, i) => tab.classList.toggle("is-active", i === activeIndex)); panels.forEach((panel, i) => panel.classList.toggle("is-active", i === activeIndex)); };
  tabs.forEach((tab, i) => tab.addEventListener("click", () => activate(i)));
  prevBtn?.addEventListener("click", () => activate(activeIndex - 1));
  nextBtn?.addEventListener("click", () => activate(activeIndex + 1));
  commentInput?.addEventListener("input", () => { countText.textContent = commentInput.value.length; });
  document.querySelectorAll(".template-btn").forEach((btn) => btn.addEventListener("click", () => { commentInput.value = commentInput.value ? `${commentInput.value}\n${btn.dataset.template}` : btn.dataset.template; commentInput.dispatchEvent(new Event("input")); }));
  document.querySelectorAll(".copy-code-btn").forEach((btn) => btn.addEventListener("click", async () => { const target = document.getElementById(btn.dataset.target); if (!target) return; await navigator.clipboard?.writeText(target.textContent || ""); btn.textContent = "복사됨"; setTimeout(() => btn.textContent = "복사", 1000); }));
  document.querySelectorAll(".history-item").forEach((btn) => btn.addEventListener("click", () => { document.querySelectorAll(".history-item").forEach(v => v.classList.remove("is-active")); btn.classList.add("is-active"); historyView.textContent = btn.dataset.code || "코드가 없습니다."; }));
  const renderSimilar = (similarNotes) => { if (!similarNotes.length) { similarEmpty.textContent = "유사 오답노트가 없습니다."; similarEmpty.hidden = false; similarBox.hidden = true; return; } similarBox.innerHTML = similarNotes.map((note) => `<article class="evidence-card"><strong>note_id ${escapeHtml(note.note_id)}</strong><span>source ${escapeHtml(note.source)}</span><span>score ${escapeHtml(note.score)}</span></article>`).join(""); similarBox.hidden = false; similarEmpty.hidden = true; };
  const renderAnalysis = (analysis, errors) => { const rows = [["문제 핵심", analysis.problem_core],["오답 원인", analysis.cause],["풀이 과정", analysis.solution],["주의사항", analysis.caution]]; analysisBox.innerHTML = rows.map(([title, body]) => `<article class="analysis-card"><strong>${title}</strong><p>${escapeHtml(body || "아직 분석 결과가 없습니다.")}</p></article>`).join(""); if (errors.length) analysisBox.innerHTML += `<pre class="result-pre result-error-text">${escapeHtml(errors.map((error) => `${error.stage}: ${error.message}`).join("\n"))}</pre>`; analysisBox.hidden = false; analysisEmpty.hidden = true; };
  saveBtn?.addEventListener("click", async () => {
    const comment = commentInput.value.trim();
    if (!comment) { statusText.textContent = "회고를 먼저 작성하세요."; activate(4); return; }
    saveBtn.disabled = true; statusText.textContent = "저장 및 AI 분석 요청 중입니다.";
    savedReflection.textContent = comment; reflectionStage.classList.remove("is-active"); feedbackStage.classList.add("is-active");
    try {
      const response = await fetch(window.location.pathname, { method:"POST", headers:{"Content-Type":"application/json", "X-CSRFToken": decodeURIComponent(getCookie("csrftoken")), "Accept":"application/json"}, body: JSON.stringify({ submission_id: Number(root.dataset.submissionId), problem_id: Number(root.dataset.problemId), comment }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.error_message || "오답노트 저장에 실패했습니다.");
      const ai = data.ai_analysis || {}; renderSimilar(ai.similar_notes || []); renderAnalysis(ai.analysis || {}, ai.errors || []); statusText.textContent = `저장 완료 · note_id ${data.wrong_note_id} · ${data.status}`;
    } catch (error) { statusText.textContent = error.message; }
    finally { saveBtn.disabled = false; }
  });
  document.getElementById("back-to-reflection-btn")?.addEventListener("click", () => { feedbackStage.classList.remove("is-active"); reflectionStage.classList.add("is-active"); });
})();
