/**
 * 미니튜터 챗봇 (좌하단 플로팅 미니 팝업)
 * - 클릭 시 입력창 패널 토글. 질문 → 응답 "말풍선"만 표시(최신 답변 1개).
 * - 대화 컨텍스트(history)는 클라이언트에 유지하고 매 요청에 함께 전송.
 * - 현재 활동(현재 페이지/문제)을 수집해 함께 전송 → 서버가 코딩상태·최근 오답(RAG)과 종합.
 */
(() => {
  const widget = document.getElementById("chatbot-widget");
  if (!widget) return;

  const askUrl = widget.dataset.askUrl;
  const fab = document.getElementById("chatbot-fab");
  const panel = document.getElementById("chatbot-panel");
  const closeBtn = document.getElementById("chatbot-close");
  const form = document.getElementById("chatbot-form");
  const input = document.getElementById("chatbot-input");
  const sendBtn = form.querySelector(".chatbot-send");
  const answerArea = document.getElementById("chatbot-answer-area");

  const history = [];            // [{role:"user"|"assistant", content}]
  const HISTORY_MAX = 8;

  const getCookie = (name) => {
    const found = (document.cookie || "").split(";").map((v) => v.trim())
      .find((v) => v.startsWith(`${name}=`));
    return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
  };

  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[ch]));

  const getProblemId = () => {
    const el = document.querySelector("[data-problem-id]");
    const raw = el && el.getAttribute("data-problem-id");
    return raw && /^\d+$/.test(raw) ? Number(raw) : undefined;
  };

  const openPanel = () => {
    panel.hidden = false;
    widget.classList.add("is-open");
    fab.setAttribute("aria-expanded", "true");
    input.focus();
  };
  const closePanel = () => {
    panel.hidden = true;
    widget.classList.remove("is-open");
    fab.setAttribute("aria-expanded", "false");
  };
  const togglePanel = () => (panel.hidden ? openPanel() : closePanel());

  fab.addEventListener("click", togglePanel);
  closeBtn.addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) closePanel();
  });

  // 최신 응답 말풍선만 렌더(질문은 작은 라벨, 답변은 버블).
  const renderAnswer = (question, answerHtml, { loading = false } = {}) => {
    answerArea.innerHTML = `
      <p class="chatbot-q-echo">Q. ${escapeHtml(question)}</p>
      <p class="chatbot-bubble ${loading ? "is-loading" : ""}">${answerHtml}</p>
    `;
    answerArea.scrollTop = 0;
  };

  const typingHtml = '<span class="chatbot-typing"><i></i><i></i><i></i></span> 생각하는 중';

  /** 질문 → 답변(Promise). 미니튜터 엔드포인트 호출(대화 이력·현재 활동 동봉). */
  const askBot = async (question) => {
    const activity = { path: location.pathname, title: document.title, problem_id: getProblemId() };
    const res = await fetch(askUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        "Accept": "application/json",
      },
      body: JSON.stringify({ question, history: history.slice(-HISTORY_MAX), activity }),
    });
    const body = await res.json().catch(() => ({}));
    const status = body.status;
    if (!res.ok || (status && status !== "success" && status !== "empty")) {
      throw new Error(body.message || "답변을 불러오지 못했어요.");
    }
    return (body.data && body.data.answer) || "지금은 답변을 만들지 못했어요. 다른 질문을 해볼까요?";
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = (input.value || "").trim();
    if (!question) { input.focus(); return; }

    input.value = "";
    sendBtn.disabled = true;
    renderAnswer(question, typingHtml, { loading: true });

    try {
      const answer = await askBot(question);
      renderAnswer(question, escapeHtml(answer));
      history.push({ role: "user", content: question }, { role: "assistant", content: answer });
      if (history.length > HISTORY_MAX * 2) history.splice(0, history.length - HISTORY_MAX * 2);
    } catch (err) {
      renderAnswer(question, escapeHtml(err.message || "답변을 불러오지 못했어요."));
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });
})();
