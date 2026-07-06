(() => {
  const questionInput = document.getElementById("note-question");
  const askButton = document.getElementById("note-ask-btn");
  const statusText = document.getElementById("note-ask-status");
  const answerBox = document.getElementById("note-answer");
  const evidenceBox = document.getElementById("note-evidence");
  const emptyGuide = document.getElementById("note-empty-guide");
  if (!questionInput || !askButton) return;
  const getCookie = (name) => (document.cookie || "").split(";").map(v=>v.trim()).find(v=>v.startsWith(`${name}=`))?.slice(name.length + 1) || "";
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const ask = async () => {
    const question = questionInput.value.trim();
    if (!question) { statusText.textContent = "질문을 입력하세요."; return; }
    answerBox.hidden = true; evidenceBox.hidden = true; if (emptyGuide) emptyGuide.hidden = true; askButton.disabled = true; statusText.textContent = "오답노트 검색 중입니다.";
    try {
      const response = await fetch(window.location.pathname, { method:"POST", headers:{"Content-Type":"application/json", "X-CSRFToken":decodeURIComponent(getCookie("csrftoken")), "Accept":"application/json"}, body: JSON.stringify({ question }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.error_message || "질문 처리에 실패했습니다.");
      statusText.textContent = `처리 완료 · ${data.status || "success"}`;
      answerBox.innerHTML = `<strong>오답노트 RAG 답변</strong><p>${escapeHtml(data.answer || "근거가 부족하거나 AI 답변 생성이 아직 구현되지 않았습니다.")}</p>`; answerBox.hidden = false;
      const ids = data.evidence_note_ids || []; const scores = data.scores || [];
      evidenceBox.innerHTML = ids.length ? ids.map((id, i) => `<span class="evidence-pill">note_id ${escapeHtml(id)} · score ${escapeHtml(scores[i] ?? "")}</span>`).join("") : `<span class="hint-note">검색된 근거 오답노트가 없습니다.</span>`;
      evidenceBox.hidden = false;
    } catch (error) { statusText.textContent = error.message; }
    finally { askButton.disabled = false; }
  };
  document.querySelectorAll(".question-preset").forEach((button) => button.addEventListener("click", () => { questionInput.value = button.dataset.question; ask(); }));
  askButton.addEventListener("click", ask);
})();
