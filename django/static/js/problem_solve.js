(() => {
  const pane = document.querySelector(".editor-pane");
  if (!pane) return;

  const codeTextarea = document.getElementById("code-editor");
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
    ? { get value() { return cm.getValue(); }, set value(v) { cm.setValue(v || ""); } }
    : codeTextarea;

  const runButton = document.getElementById("run-code-btn");
  const submitButton = document.getElementById("submit-btn");
  const resetButton = document.getElementById("reset-code-btn");
  const loadingBox = document.getElementById("run-loading-box");
  const errorBox = document.getElementById("run-error-box");
  const statusBox = document.getElementById("result-status-box");
  const emptyResultBox = document.querySelector("[data-result-empty]");
  const wrongNoteLink = document.getElementById("wrong-note-create-link");
  const wrongNoteHelp = document.getElementById("wrong-note-help");
  const hintNextButton = document.getElementById("hint-next-btn");
  const autosaveNote = document.querySelector(".autosave-note");
  const defaultWrongNoteHelp = wrongNoteHelp ? wrongNoteHelp.textContent : "";
  const draftKey = `wooks-code-draft-${pane.dataset.problemId}`;
  let unlockedHintLevel = 0;

  const getCookie = (name) => (document.cookie || "")
    .split(";")
    .map((v) => v.trim())
    .find((v) => v.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";

  const showText = (el, text) => {
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
  };

  const hide = (...els) => els.forEach((el) => {
    if (el) el.hidden = true;
  });

  const show = (...els) => els.forEach((el) => {
    if (el) el.hidden = false;
  });

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[c]));

  const updateAutosaveText = (message = "자동 저장됨") => {
    if (!autosaveNote) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    autosaveNote.textContent = `${message} ${time}`;
  };

  const restoreDraft = () => {
    try {
      const saved = localStorage.getItem(draftKey);
      if (saved && !editor.value.trim()) {
        editor.value = saved;
        updateAutosaveText("임시 코드 복원");
      }
    } catch (_) {
      // localStorage가 막힌 환경에서는 조용히 무시합니다.
    }
  };

  const saveDraft = () => {
    try {
      localStorage.setItem(draftKey, editor.value);
      updateAutosaveText();
    } catch (_) {
      if (autosaveNote) autosaveNote.textContent = "자동 저장 불가";
    }
  };

  const debounce = (fn, delay = 450) => {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  };

  restoreDraft();
  const debouncedSaveDraft = debounce(saveDraft);
  if (cm) {
    cm.on("change", debouncedSaveDraft);
  } else {
    codeTextarea?.addEventListener("input", debouncedSaveDraft);
  }

  const updateWrongNoteLink = (data) => {
    if (!wrongNoteLink) return;
    if (data.wrong_note_create_url) {
      wrongNoteLink.href = data.wrong_note_create_url;
      if (wrongNoteHelp) wrongNoteHelp.textContent = "현재 제출 결과로 오답노트를 작성할 수 있습니다.";
    } else {
      wrongNoteLink.href = pane.dataset.wrongnoteListUrl;
      if (wrongNoteHelp) wrongNoteHelp.textContent = defaultWrongNoteHelp;
    }
  };

  const setResultState = (resultLabel) => {
    if (!statusBox) return;
    statusBox.classList.remove("state-success", "state-failed", "state-wrong", "state-error");
    const normalized = String(resultLabel || "").toLowerCase();
    if (["correct", "success", "accepted", "passed"].includes(normalized)) {
      statusBox.classList.add("state-success");
    } else if (normalized.includes("wrong")) {
      statusBox.classList.add("state-wrong");
    } else if (normalized.includes("error")) {
      statusBox.classList.add("state-error");
    } else if (normalized.includes("fail")) {
      statusBox.classList.add("state-failed");
    }
  };

  const renderResult = (data) => {
    const resultLabel = data.submission_result || "pending";
    const passed = data.total ? `${escapeHtml(data.passed)}/${escapeHtml(data.total)}` : "-";
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
        <span>실행 시간 ${escapeHtml(data.elapsed_ms || 0)}ms</span>
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
    setResultState(resultLabel);
    hide(emptyResultBox);
    show(statusBox);
  };

  statusBox?.addEventListener("click", (event) => {
    const tabButton = event.target.closest(".result-tab");
    if (!tabButton) return;
    const targetTab = tabButton.dataset.tab;
    statusBox.querySelectorAll(".result-tab").forEach((btn) => btn.classList.toggle("active", btn === tabButton));
    statusBox.querySelectorAll(".result-tab-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== targetTab;
    });
  });

  const pollResult = async (submissionId) => {
    for (let i = 0; i < 20; i += 1) {
      const response = await fetch(pane.dataset.resultUrlTemplate.replace("__ID__", submissionId), {
        headers: { "Accept": "application/json" },
      });
      if (!response.ok) throw new Error("결과 조회에 실패했습니다.");
      const data = await response.json();
      if (data.is_finished) {
        updateWrongNoteLink(data);
        renderResult(data);
        hide(loadingBox);
        return;
      }
      hide(emptyResultBox);
      showText(loadingBox, `채점 중입니다. Job: ${data.job_status} · ${i + 1}/20`);
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    throw new Error("결과 대기 시간이 초과되었습니다. Worker 상태를 확인하세요.");
  };

  const createJob = async (url, queuedMessage) => {
    hide(errorBox, statusBox, emptyResultBox);
    showText(loadingBox, queuedMessage);
    runButton.disabled = true;
    submitButton.disabled = true;

    try {
      saveDraft();
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
        await pollResult(data.submission_id);
      }
    } catch (error) {
      hide(loadingBox, emptyResultBox);
      showText(errorBox, error.message);
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
    if (!toggle || !body) return;

    hintNextButton.disabled = true;
    body.hidden = false;
    showText(body, "힌트를 생성 중입니다…");

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
        hintStepEl(level)?.classList.add("unlocked");
        toggle.disabled = false;
        const lockLabel = toggle.querySelector(".lock-label");
        if (lockLabel) lockLabel.outerHTML = '<span class="chevron">▾</span>';
        unlockedHintLevel = level;
        hintNextButton.textContent = level >= 3 ? "모든 힌트를 확인했습니다" : "다음 힌트 요청";
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
    try { localStorage.removeItem(draftKey); } catch (_) {}
    if (autosaveNote) autosaveNote.textContent = "초기화됨";
    hide(errorBox, statusBox, loadingBox);
    show(emptyResultBox);
  });
  hintNextButton?.addEventListener("click", () => requestHint(unlockedHintLevel + 1));
  document.querySelectorAll(".hint-step-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      if (toggle.disabled) return;
      const body = hintBodyEl(toggle.dataset.level);
      if (body) body.hidden = !body.hidden;
    });
  });
})();
