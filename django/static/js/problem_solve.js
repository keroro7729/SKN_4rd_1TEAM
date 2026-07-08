(() => {
  const pane = document.querySelector(".editor-pane");
  if (!pane) return;

  const solvePage = document.querySelector(".solve-page");
  const questLabel = document.getElementById("quest-status-label");
  const questText = document.getElementById("quest-status-text");
  const battleState = document.getElementById("battle-state");
  const stateLabelMap = {
    reading: "READ",
    coding: "CODE",
    running: "RUN",
    success: "CLEAR",
    failed: "RETRY",
    hint: "HINT",
  };
  const stageMap = {
    reading: "reading",
    coding: "coding",
    hint: "coding",
    running: "running",
    success: "clear",
    failed: "clear",
  };
  const setQuestState = (state, label, text) => {
    if (!solvePage) return;
    solvePage.classList.remove("is-reading", "is-coding", "is-running", "is-success", "is-failed", "is-hint");
    if (state) solvePage.classList.add(`is-${state}`);
    if (state) solvePage.dataset.questStage = stageMap[state] || state;
    document.querySelectorAll("[data-stage-step]").forEach((step) => {
      const activeStage = stageMap[state] || state;
      step.classList.toggle("active", step.dataset.stageStep === activeStage);
      step.classList.toggle("done", ["coding", "running", "clear"].includes(activeStage) && step.dataset.stageStep === "reading");
      step.classList.toggle("done", ["running", "clear"].includes(activeStage) && step.dataset.stageStep === "coding");
      step.classList.toggle("done", activeStage === "clear" && step.dataset.stageStep === "running");
    });
    if (questLabel && label) questLabel.textContent = label;
    if (questText && text) questText.textContent = text;
    if (battleState && state) battleState.textContent = stateLabelMap[state] || state.toUpperCase();
  };

  const codeTextarea = document.getElementById("code-editor");
  const autosaveNote = document.getElementById("autosave-note");
  const storageKey = `wooks:problem:${pane.dataset.problemId}:draft`;

  const cm = window.CodeMirror ? CodeMirror.fromTextArea(codeTextarea, {
    mode: "python",
    theme: "dracula",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    matchBrackets: true,
    viewportMargin: Infinity,
  }) : null;

  const editor = cm
    ? { get value(){ return cm.getValue(); }, set value(v){ cm.setValue(v); } }
    : codeTextarea;

  const savedCode = localStorage.getItem(storageKey);
  if (savedCode && !editor.value.trim()) {
    editor.value = savedCode;
    if (autosaveNote) autosaveNote.textContent = "임시 저장 복원됨";
    setQuestState("coding", "이어하기", "저장된 풀이를 복원했습니다. 이어서 코딩 배틀을 진행하세요.");
  } else {
    setQuestState("reading", "브리핑 확인", "문제 원문을 읽고 조건·예제를 확인한 뒤 풀이를 시작하세요.");
  }

  let saveTimer = null;
  const persistCode = () => {
    setQuestState("coding", "코드 작성 중", "배틀 콘솔에서 풀이를 구현 중입니다. 실행 버튼으로 테스트를 확인하세요.");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      localStorage.setItem(storageKey, editor.value);
      if (autosaveNote) {
        const now = new Date();
        autosaveNote.textContent = `저장됨 ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      }
    }, 220);
  };
  if (cm) cm.on("change", persistCode);
  else codeTextarea.addEventListener("input", persistCode);

  const runButton = document.getElementById("run-code-btn");
  const submitButton = document.getElementById("submit-btn");
  const resetButton = document.getElementById("reset-code-btn");
  const loadingBox = document.getElementById("run-loading-box");
  const errorBox = document.getElementById("run-error-box");
  const statusBox = document.getElementById("result-status-box");
  const wrongNoteLink = document.getElementById("wrong-note-create-link");
  const wrongNoteHeaderLink = document.getElementById("wrong-note-header-link");
  const wrongNoteHelp = document.getElementById("wrong-note-help");
  const hintNextButton = document.getElementById("hint-next-btn");
  const defaultWrongNoteHelp = wrongNoteHelp ? wrongNoteHelp.textContent : "";
  let unlockedHintLevel = 0;

  const getCookie = (name) => (document.cookie || "")
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";

  const showText = (element, text) => {
    if (!element) return;
    element.textContent = text;
    element.hidden = false;
  };
  const hide = (...elements) => elements.forEach((element) => {
    if (element) element.hidden = true;
  });
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const updateWrongNoteLink = (data) => {
    if (!wrongNoteLink) return;
    const target = data.wrong_note_create_url || pane.dataset.wrongnoteListUrl;
    wrongNoteLink.href = target;
    if (wrongNoteHeaderLink) wrongNoteHeaderLink.href = target;
    if (data.wrong_note_create_url) {
      wrongNoteHelp.textContent = "현재 제출 결과로 오답노트를 작성할 수 있습니다.";
    } else {
      wrongNoteHelp.textContent = defaultWrongNoteHelp;
    }
  };

  const resultLooksSuccess = (data) => {
    const label = String(data.submission_result || data.job_status || "").toLowerCase();
    if (data.total && Number(data.passed) === Number(data.total)) return true;
    return ["correct", "success", "accepted", "passed", "completed"].some((word) => label.includes(word));
  };

  const renderResult = (data) => {
    const resultLabel = data.submission_result || "pending";
    const passed = data.total ? `${data.passed}/${data.total}` : "-";
    const caseRows = (data.case_results || []).map((item) => {
      const detailParts = [];
      if (item.input !== undefined) detailParts.push(`입력 ${escapeHtml(item.input)}`);
      if (item.expected !== undefined) detailParts.push(`기대 ${escapeHtml(item.expected)}`);
      if (item.actual !== undefined) detailParts.push(`출력 ${escapeHtml(item.actual)}`);
      if (item.error) detailParts.push(escapeHtml(item.error));
      const detail = detailParts.length ? `<span class="case-detail">${detailParts.join(" · ")}</span>` : "";
      return `<li class="${item.passed ? "case-pass" : "case-fail"}"><span class="case-mark">${item.passed ? "✓" : "✗"}</span>TC${escapeHtml(item.case)}${detail}</li>`;
    }).join("");

    statusBox.innerHTML = `
      <div class="result-header">
        <strong>결과: ${escapeHtml(resultLabel)}</strong>
        <span>Job: ${escapeHtml(data.job_status)}</span>
        <span>테스트 ${passed}</span>
        <span>실행 시간 ${data.elapsed_ms || 0}ms</span>
      </div>
      <div class="result-tabs">
        <button type="button" class="result-tab active" data-tab="cases">테스트케이스</button>
        <button type="button" class="result-tab" data-tab="stdout">stdout</button>
      </div>
      <div class="result-tab-panel" data-panel="cases">
        ${caseRows ? `<ul class="case-list">${caseRows}</ul>` : '<p class="hint-note">표시할 테스트케이스 결과가 없습니다.</p>'}
      </div>
      <div class="result-tab-panel" data-panel="stdout" hidden>
        ${data.output ? `<pre class="result-pre">${escapeHtml(data.output)}</pre>` : '<p class="hint-note">표준출력이 없습니다.</p>'}
        ${data.error_message ? `<pre class="result-pre result-error-text">${escapeHtml(data.error_message)}</pre>` : ""}
      </div>
    `;
    statusBox.hidden = false;

    if (resultLooksSuccess(data)) {
      setQuestState("success", "Quest Clear", "테스트를 통과했습니다. 다음 퀘스트로 이동하거나 풀이 기록을 확인하세요.");
    } else {
      setQuestState("failed", "Retry Quest", "통과하지 못한 케이스를 확인하고, 오답노트로 실수 원인을 정리해보세요.");
    }
  };

  statusBox?.addEventListener("click", (event) => {
    const tabButton = event.target.closest(".result-tab");
    if (!tabButton) return;
    const targetTab = tabButton.dataset.tab;
    statusBox.querySelectorAll(".result-tab").forEach((button) => {
      button.classList.toggle("active", button === tabButton);
    });
    statusBox.querySelectorAll(".result-tab-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== targetTab;
    });
  });

  const pollResult = async (submissionId) => {
    // 최초 1회 TC 자동생성(수십 초 소요 가능)을 고려해 벽시계 예산으로 대기한다.
    const POLL_INTERVAL_MS = 700;
    const MAX_WAIT_MS = 180000; // 3분
    const started = Date.now();
    while (Date.now() - started < MAX_WAIT_MS) {
      const response = await fetch(pane.dataset.resultUrlTemplate.replace("__ID__", submissionId), {
        headers: {"Accept": "application/json"},
      });
      if (!response.ok) throw new Error("결과 조회에 실패했습니다.");
      const data = await response.json();
      if (data.is_finished) {
        updateWrongNoteLink(data);
        renderResult(data);
        hide(loadingBox);
        return;
      }
      if (data.job_status === "generating") {
        setQuestState("running", "테스트케이스 생성", "이 문제의 테스트케이스를 처음 만드는 중입니다. 최초 1회만 시간이 걸립니다…");
        showText(loadingBox, "테스트케이스를 생성하는 중입니다. 최초 1회만 시간이 걸려요…");
      } else {
        setQuestState("running", "채점 중", "테스트케이스를 순서대로 확인하고 있습니다.");
        showText(loadingBox, `채점 중입니다. Job: ${data.job_status}`);
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
    throw new Error("결과 대기 시간이 초과되었습니다. Worker 상태를 확인하세요.");
  };

  const createJob = async (url, queuedMessage) => {
    hide(errorBox, statusBox);
    showText(loadingBox, queuedMessage);
    setQuestState("running", "런 타임 진입", "코드를 실행 환경에 보내고 있습니다. 테스트 결과를 기다려주세요.");
    runButton.disabled = true;
    submitButton.disabled = true;
    persistCode();
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(getCookie("csrftoken")),
          "Accept": "application/json",
        },
        body: JSON.stringify({
          problem_id: Number(pane.dataset.problemId),
          code: editor.value,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error_message || "요청에 실패했습니다.");
      if (data.is_finished) {
        updateWrongNoteLink(data);
        renderResult(data);
        hide(loadingBox);
      } else {
        showText(loadingBox, "결과 확인 중입니다.");
        setQuestState("running", "테스트 배틀", "테스트케이스를 순서대로 확인하고 있습니다.");
        await pollResult(data.submission_id);
      }
    } catch (error) {
      hide(loadingBox);
      showText(errorBox, error.message);
      setQuestState("failed", "실행 오류", "오류 메시지를 확인하고 코드나 실행 환경을 점검하세요.");
    } finally {
      runButton.disabled = false;
      submitButton.disabled = false;
    }
  };

  const hintStepEl = (level) => document.querySelector(`.hint-step[data-level="${level}"]`);
  const hintToggleEl = (level) => document.querySelector(`.hint-step-toggle[data-level="${level}"]`);
  const hintBodyEl = (level) => document.getElementById(`hint-body-${level}`);

  const requestHint = async (level) => {
    const toggle = hintToggleEl(level);
    const body = hintBodyEl(level);
    hintNextButton.disabled = true;
    body.hidden = false;
    showText(body, "힌트를 생성 중입니다…");
    setQuestState("hint", "Sidekick 호출", "AI 파트너가 현재 코드와 문제를 기준으로 단계별 힌트를 준비합니다.");
    try {
      const response = await fetch(pane.dataset.hintUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(getCookie("csrftoken")),
          "Accept": "application/json",
        },
        body: JSON.stringify({
          problem_id: Number(pane.dataset.problemId),
          hint_level: Number(level),
          user_code: editor.value,
        }),
      });
      const data = await response.json();
      const content = data.data && data.data.content ? data.data.content : "";
      if (data.status === "success") {
        showText(body, content);
        hintStepEl(level).classList.add("unlocked");
        toggle.disabled = false;
        toggle.querySelector(".lock-label").outerHTML = '<span class="chevron">▾</span>';
        unlockedHintLevel = level;
        hintNextButton.textContent = level >= 3 ? "모든 힌트를 확인했습니다" : "다음 힌트 요청";
        setQuestState("hint", `힌트 ${level}단계 해금`, "힌트를 참고해서 풀이 방향을 다시 점검해보세요.");
      } else {
        showText(body, `힌트 생성 상태: ${data.message || data.status} · request_id ${data.request_id || "-"}`);
      }
    } catch (error) {
      showText(body, error.message);
    } finally {
      if (unlockedHintLevel < 3) hintNextButton.disabled = false;
    }
  };

  runButton?.addEventListener("click", () => createJob(pane.dataset.runUrl, "실행 대기열에 등록 중입니다."));
  submitButton?.addEventListener("click", () => createJob(pane.dataset.submitUrl, "제출 대기열에 등록 중입니다."));
  resetButton?.addEventListener("click", () => {
    editor.value = "";
    localStorage.removeItem(storageKey);
    if (autosaveNote) autosaveNote.textContent = "초기화됨";
    hide(errorBox, statusBox, loadingBox);
    setQuestState("reading", "새 도전", "문제를 다시 확인하고 새로운 풀이 루트를 시작하세요.");
  });
  hintNextButton?.addEventListener("click", () => requestHint(unlockedHintLevel + 1));
  document.querySelectorAll(".hint-step-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      if (toggle.disabled) return;
      const body = hintBodyEl(toggle.dataset.level);
      body.hidden = !body.hidden;
    });
  });

  const reader = document.querySelector("[data-reader]");
  const problemScroll = document.querySelector(".problem-scroll");
  const progress = document.querySelector(".reader-progress");
  reader?.querySelectorAll("[data-problem-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      reader.dataset.mode = button.dataset.problemMode;
      reader.querySelectorAll("[data-problem-mode]").forEach((item) => item.classList.toggle("active", item === button));
      problemScroll?.scrollTo({top: 0, behavior: "smooth"});
      const modeLabel = button.textContent.trim();
      setQuestState("reading", `${modeLabel} 브리핑`, "필요한 문제 섹션만 골라 보고 코드 작성 흐름을 유지하세요.");
    });
  });

  document.querySelectorAll("[data-scroll-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.scrollTarget);
      if (!target || !problemScroll) return;
      const top = target.offsetTop - problemScroll.offsetTop - 8;
      problemScroll.scrollTo({top, behavior: "smooth"});
      setQuestState("reading", "브리핑 이동", `${button.textContent.trim()} 섹션으로 이동했습니다.`);
    });
  });

  const readerPercent = document.getElementById("reader-percent");
  const updateReaderProgress = () => {
    if (!problemScroll) return;
    const max = problemScroll.scrollHeight - problemScroll.clientHeight;
    const pct = max > 0 ? Math.min(100, Math.round((problemScroll.scrollTop / max) * 100)) : 100;
    progress?.style.setProperty("--reader-progress", `${pct}%`);
    if (readerPercent) readerPercent.textContent = `${pct}%`;
  };
  problemScroll?.addEventListener("scroll", updateReaderProgress);
  updateReaderProgress();

  const checkCount = document.getElementById("check-count");
  const updateQuestChecks = () => {
    const checks = Array.from(document.querySelectorAll("[data-quest-check]"));
    const done = checks.filter((item) => item.checked).length;
    if (checkCount) checkCount.textContent = `${done}/${checks.length || 4}`;
    if (done > 0) setQuestState("coding", "체크 진행", `풀이 전 체크 ${done}/${checks.length || 4}개를 확인했습니다.`);
  };
  document.querySelectorAll("[data-quest-check]").forEach((check) => check.addEventListener("change", updateQuestChecks));
  updateQuestChecks();

  document.querySelectorAll(".copy-sample-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copyText || "");
        const original = button.textContent;
        button.textContent = "복사됨";
        setQuestState("coding", "예제 입력 복사", "복사한 입력으로 직접 실행해보며 풀이를 검증하세요.");
        setTimeout(() => { button.textContent = original; }, 1200);
      } catch (_) {
        button.textContent = "복사 실패";
      }
    });
  });
})();
