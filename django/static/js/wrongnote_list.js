(() => {
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

  document.querySelectorAll(".review-note-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = "처리 중...";
      try {
        const response = await fetch(button.dataset.reviewUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Accept": "application/json",
          },
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error_message || "복습 완료 처리에 실패했습니다.");
        }
        const label = document.createElement("span");
        label.className = "game-state success";
        label.textContent = data.point_created ? "✓ 복습완료 +10P" : "✓ 복습완료";
        button.replaceWith(label);
      } catch (error) {
        button.disabled = false;
        button.textContent = error.message || originalText;
      }
    });
  });
})();
