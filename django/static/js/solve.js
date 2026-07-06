/* WOOK'S CODING - 문제풀이 실행/제출 Fetch 연동 (STEP-07 선반영)
 * 실행(run): 1번 테스트케이스만 실행 → 입력/기대정답/실행결과 표시
 * 제출(submit): 전체 테스트케이스 채점 → 통과 수/판정 표시
 * /submissions/run/ 로 POST(job 생성) → /submissions/<id>/result/ 폴링.
 */
(function () {
  "use strict";
  const pane = document.querySelector(".editor-pane");
  if (!pane) return;

  const problemId = pane.dataset.problemId;
  const codeEl = document.getElementById("code-input");
  const runBtn = document.getElementById("run-btn");
  const submitBtn = document.getElementById("submit-btn");
  const area = document.getElementById("result-area");

  function csrftoken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function esc(s) {
    return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])
    );
  }

  function show(html, state) {
    area.hidden = false;
    area.className = "result-area " + (state || "");
    area.innerHTML = html;
  }

  function setBusy(busy) {
    runBtn.disabled = submitBtn.disabled = busy;
  }

  async function submitCode(mode) {
    const code = codeEl.value;
    if (!code.trim()) {
      show("코드를 입력하세요.", "state-empty");
      return;
    }
    setBusy(true);
    show(mode === "run" ? "실행 중…" : "채점 중…", "state-loading");
    try {
      const res = await fetch("/submissions/run/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken() },
        body: JSON.stringify({ problem_id: problemId, code: code, mode: mode }),
      });
      if (!res.ok) {
        show("요청 실패 (" + res.status + ")", "state-failed");
        return;
      }
      const { submission_id } = await res.json();
      await poll(submission_id, mode);
    } catch (e) {
      show("네트워크 오류: " + esc(e.message), "state-failed");
    } finally {
      setBusy(false);
    }
  }

  function poll(sid, mode) {
    return new Promise((resolve) => {
      let tries = 0;
      const timer = setInterval(async () => {
        tries += 1;
        let d;
        try {
          d = await (await fetch("/submissions/" + sid + "/result/")).json();
        } catch (_) {
          return; // 일시 오류는 다음 폴링에서 재시도
        }
        if (!d.is_finished) {
          if (tries > 40) {
            clearInterval(timer);
            show("응답 지연 — 잠시 후 다시 시도하세요.", "state-timeout");
            resolve();
          }
          return;
        }
        clearInterval(timer);
        render(d, mode);
        resolve();
      }, 700);
    });
  }

  function stateOf(result) {
    if (result === "success") return "state-success";
    if (result === "timeout") return "state-timeout";
    if (result === "empty") return "state-empty";
    return "state-failed"; // wrong / error 등
  }

  function render(d, mode) {
    const detail = d.detail || {};
    const r = d.submission_result;
    const ms = d.elapsed_ms == null ? "-" : d.elapsed_ms;
    const badge =
      '<span class="badge badge-status-' + esc(r) + '">' + esc(r) + "</span>";

    let html;
    if (mode === "run") {
      html =
        '<div class="rc-line"><b>실행 결과</b> ' + badge +
        ' <span class="rc-ms">' + ms + "ms</span></div>" +
        '<div class="rc-io">' +
        "<div><b>입력</b><pre>" + esc(detail.input) + "</pre></div>" +
        "<div><b>기대정답</b><pre>" + esc(detail.expected) + "</pre></div>" +
        "<div><b>실행결과</b><pre>" + esc(detail.actual != null ? detail.actual : d.output) + "</pre></div>" +
        "</div>";
    } else {
      const passed = detail.passed == null ? 0 : detail.passed;
      const total = detail.total == null ? 0 : detail.total;
      html =
        '<div class="rc-line"><b>채점</b> ' + badge +
        ' <span class="rc-ms">' + passed + "/" + total + " 통과 · " + ms + "ms</span></div>";
    }
    if (d.error_message) {
      html += "<div class=\"rc-err\"><b>에러</b><pre>" + esc(d.error_message) + "</pre></div>";
    }
    show(html, stateOf(r));
  }

  runBtn.addEventListener("click", () => submitCode("run"));
  submitBtn.addEventListener("click", () => submitCode("submit"));
})();
