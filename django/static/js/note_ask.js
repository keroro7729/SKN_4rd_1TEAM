(() => {
  const questionInput = document.getElementById("note-question");
  const askButton = document.getElementById("note-ask-btn");
  const statusText = document.getElementById("note-ask-status");
  const answerBox = document.getElementById("note-answer");
  const evidenceBox = document.getElementById("note-evidence");
  const emptyBox = document.getElementById("ask-empty");
  const previewBox = document.getElementById("ask-preview");

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

  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const setStatus = (text, tone = "cyan") => {
    statusText.textContent = text;
    statusText.className = `game-chip ${tone}`;
  };

  const ask = async () => {
    const question = questionInput.value.trim();
    if (!question) {
      setStatus("질문을 입력하세요", "muted");
      return;
    }

    if (previewBox) {
      previewBox.textContent = question;
      previewBox.hidden = false;
    }
    if (emptyBox) emptyBox.hidden = true;
    answerBox.hidden = true;
    evidenceBox.hidden = true;
    askButton.disabled = true;
    askButton.textContent = "검색 중...";
    setStatus("오답노트 검색 중", "cyan");

    try {
      const response = await fetch(window.location.pathname, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
        },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error_message || "질문 처리에 실패했습니다.");
      }

      setStatus(`처리 완료 · ${data.status || "ok"}`, "cyan");
      answerBox.innerHTML = `
        <strong>🤖 오답노트 RAG 답변</strong>
        <p>${escapeHtml(data.answer || "근거가 부족하거나 AI 답변 생성이 아직 구현되지 않았습니다.")}</p>
      `;
      answerBox.hidden = false;

      const ids = data.evidence_note_ids || [];
      const scores = data.scores || [];
      evidenceBox.innerHTML = ids.length
        ? ids.map((id, index) => `<span class="evidence-pill">note_id ${escapeHtml(id)} · score ${escapeHtml(scores[index] ?? "")}</span>`).join("")
        : `<span class="game-muted">검색된 근거 오답노트가 없습니다.</span>`;
      evidenceBox.hidden = false;
    } catch (error) {
      setStatus(error.message, "muted");
    } finally {
      askButton.disabled = false;
      askButton.textContent = "질문";
    }
  };

  document.querySelectorAll(".question-preset").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question;
      ask();
    });
  });

  askButton.addEventListener("click", ask);
  questionInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") ask();
  });

  if (questionInput.value.trim()) {
    if (previewBox) {
      previewBox.textContent = questionInput.value.trim();
      previewBox.hidden = false;
    }
  }
})();
