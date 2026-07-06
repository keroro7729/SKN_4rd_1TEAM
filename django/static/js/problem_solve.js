(() => {
  const pane = document.querySelector(".editor-pane");

  // 기존 <textarea id="code-editor">를 CodeMirror 에디터로 바꿔서
  // 주석/문자열/변수/키워드가 각각 다른 색으로 강조되게 합니다.
  const codeTextarea = document.getElementById("code-editor");
  const cm = CodeMirror.fromTextArea(codeTextarea, {
    mode: "python",
    theme: "dracula",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    matchBrackets: true,
    viewportMargin: Infinity,
  });
  // 아래 코드 전체에서 editor.value로 읽고 쓰던 부분을 그대로 쓸 수 있도록,
  // value를 CodeMirror와 연결된 getter/setter로 만들어줍니다.
  const editor = {
    get value() { return cm.getValue(); },
    set value(v) { cm.setValue(v); },
  };

  const runButton = document.getElementById("run-code-btn");
  const submitButton = document.getElementById("submit-btn");
  const resetButton = document.getElementById("reset-code-btn");
  const loadingBox = document.getElementById("run-loading-box");
  const errorBox = document.getElementById("run-error-box");
  const statusBox = document.getElementById("result-status-box");
  const wrongNoteLink = document.getElementById("wrong-note-create-link");
  const wrongNoteHelp = document.getElementById("wrong-note-help");
  const hintNextButton = document.getElementById("hint-next-btn");
  const defaultWrongNoteHelp = wrongNoteHelp.textContent;
  let unlockedHintLevel = 0;

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

  const showText = (element, text) => {
    element.textContent = text;
    element.hidden = false;
  };

  const hide = (...elements) => elements.forEach((element) => { element.hidden = true; });

  const updateWrongNoteLink = (data) => {
    if (data.wrong_note_create_url) {
      wrongNoteLink.href = data.wrong_note_create_url;
      wrongNoteHelp.textContent = "현재 제출 결과로 오답노트를 작성할 수 있습니다.";
    } else {
      wrongNoteLink.href = pane.dataset.wrongnotesListUrl || "/wrongnotes/";
      wrongNoteHelp.textContent = defaultWrongNoteHelp;
    }
  };

  const renderResult = (data) => {
    const resultLabel = data.submission_result || "pending";
    const passed = data.total ? `${data.passed}/${data.total}` : "-";
    const caseRows = (data.case_results || []).map((item) => {
      // 참고: input/expected/output 상세 표시는 백엔드(worker/main.py, submissions/views.py)에서
      // case_results에 해당 필드를 내려줘야 표시됩니다. 지금은 없으면 자동으로 생략됩니다.
      const detailParts = [];
      if (item.input !== undefined) detailParts.push(`입력 ${item.input}`);
      if (item.expected !== undefined) detailParts.push(`기대 ${item.expected}`);
      if (item.actual !== undefined) detailParts.push(`출력 ${item.actual}`);
      if (item.error) detailParts.push(item.error);
      const detail = detailParts.length ? `<span class="case-detail">${detailParts.join(" · ")}</span>` : "";
      return `<li class="${item.passed ? "case-pass" : "case-fail"}">` +
        `<span class="case-mark">${item.passed ? "✓" : "✗"}</span>TC${item.case}${detail}</li>`;
    }).join("");
    statusBox.innerHTML = `
      <div class="result-header">
        <strong>결과: ${resultLabel}</strong>
        <span>Job: ${data.job_status}</span>
        <span>테스트 ${passed}</span>
        <span>실행 시간 ${data.elapsed_ms || 0}ms</span>
      </div>
      <div class="result-tabs">
        <button type="button" class="result-tab active" data-tab="cases">테스트케이스</button>
        <button type="button" class="result-tab" data-tab="stdout">실행 결과(stdout)</button>
      </div>
      <div class="result-tab-panel" data-panel="cases">
        ${caseRows ? `<ul class="case-list">${caseRows}</ul>` : '<p class="hint-note">표시할 테스트케이스 결과가 없습니다.</p>'}
      </div>
      <div class="result-tab-panel" data-panel="stdout" hidden>
        ${data.output ? `<pre class="result-pre">${data.output}</pre>` : '<p class="hint-note">표준출력이 없습니다.</p>'}
        ${data.error_message ? `<pre class="result-pre result-error-text">${data.error_message}</pre>` : ""}
      </div>
    `;
    statusBox.hidden = false;
  };

  // 결과 박스는 매번 innerHTML로 새로 그려지므로, 버튼 각각이 아니라
  // statusBox 자체에 이벤트를 걸어두는 방식(이벤트 위임)을 사용합니다.
  statusBox.addEventListener("click", (event) => {
    const tabButton = event.target.closest(".result-tab");
    if (!tabButton) return;
    const targetTab = tabButton.dataset.tab;
    statusBox.querySelectorAll(".result-tab").forEach((btn) => {
      btn.classList.toggle("active", btn === tabButton);
    });
    statusBox.querySelectorAll(".result-tab-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== targetTab;
    });
  });

  const pollResult = async (submissionId) => {
    const maxPollCount = 20;
    for (let i = 0; i < maxPollCount; i += 1) {
      const response = await fetch(`/submissions/${submissionId}/result/`, {
        headers: {"Accept": "application/json"},
      });
      if (!response.ok) {
        throw new Error("결과 조회에 실패했습니다.");
      }
      const data = await response.json();
      if (data.is_finished) {
        updateWrongNoteLink(data);
        renderResult(data);
        hide(loadingBox);
        return;
      }
      showText(loadingBox, `채점 중입니다. Job: ${data.job_status} · ${i + 1}/${maxPollCount}`);
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    throw new Error("결과 대기 시간이 초과되었습니다. Worker 상태를 확인하세요.");
  };

  const createJob = async (url, queuedMessage) => {
    hide(errorBox, statusBox);
    wrongNoteLink.href = pane.dataset.wrongnotesListUrl || "/wrongnotes/";
    wrongNoteHelp.textContent = "오답 제출 후에는 바로 작성 화면으로 이동합니다.";
    showText(loadingBox, queuedMessage);
    runButton.disabled = true;
    submitButton.disabled = true;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
        },
        body: JSON.stringify({
          problem_id: Number(pane.dataset.problemId),
          code: editor.value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error_message || "요청에 실패했습니다.");
      }
      if (data.is_finished) {
        updateWrongNoteLink(data);
        renderResult(data);
        hide(loadingBox);
      } else {
        showText(loadingBox, "결과 확인 중입니다. 응답이 없으면 잠시 후 다시 확인합니다.");
        await pollResult(data.submission_id);
      }
    } catch (error) {
      hide(loadingBox);
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
    hintNextButton.disabled = true;
    body.hidden = false;
    showText(body, "힌트를 생성 중입니다… (대기 상태 · Timeout 시 안내)");
    try {
      const response = await fetch(pane.dataset.hintUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
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
        if (level >= 3) {
          hintNextButton.disabled = true;
          hintNextButton.textContent = "모든 힌트를 확인했습니다";
        } else {
          hintNextButton.textContent = "다음 힌트 요청";
        }
      } else {
        showText(body, `힌트 생성 상태: ${data.message || data.status} · request_id ${data.request_id || "-"}`);
      }
    } catch (error) {
      showText(body, error.message);
    } finally {
      if (unlockedHintLevel < 3) {
        hintNextButton.disabled = false;
      }
    }
  };

  runButton.addEventListener("click", () => {
    createJob(pane.dataset.runUrl, "실행 대기열에 등록 중입니다.");
  });
  submitButton.addEventListener("click", () => {
    createJob(pane.dataset.submitUrl, "제출 대기열에 등록 중입니다.");
  });
  resetButton.addEventListener("click", () => {
    editor.value = "";
    hide(errorBox, statusBox, loadingBox);
  });

  hintNextButton.addEventListener("click", () => {
    requestHint(unlockedHintLevel + 1);
  });

  document.querySelectorAll(".hint-step-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const level = toggle.dataset.level;
      if (toggle.disabled) return; // 잠긴(아직 요청 안 한) 단계는 열리지 않음
      const body = hintBodyEl(level);
      body.hidden = !body.hidden;
    });
  });
})();
