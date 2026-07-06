(() => {
  const button = document.getElementById("review-note-btn");
  if (!button) return;
  const getCookie = (name) => (document.cookie || "").split(";").map(v=>v.trim()).find(v=>v.startsWith(`${name}=`))?.slice(name.length + 1) || "";
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const response = await fetch(button.dataset.reviewUrl, { method: "POST", headers: {"X-CSRFToken": decodeURIComponent(getCookie("csrftoken")), "Accept":"application/json"} });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error_message || "복습 완료 처리에 실패했습니다.");
      const label = document.createElement("span"); label.className = "reviewed"; label.textContent = "복습완료"; button.replaceWith(label);
    } catch (error) { button.disabled = false; button.textContent = error.message; }
  });
})();
