// PROFILE_AVATAR_POPUP_V45: 상단/마이페이지 프로필 클릭 시 동물 프로필 상점 팝업 열기
(() => {
  const modal = document.getElementById("profileAvatarModal");
  if (!modal) return;

  const openButtons = document.querySelectorAll("[data-avatar-modal-open]");
  const closeButtons = modal.querySelectorAll("[data-avatar-modal-close]");

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("avatar-modal-open");
    const firstButton = modal.querySelector("button:not([disabled])");
    if (firstButton) firstButton.focus({ preventScroll: true });
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("avatar-modal-open");
  };

  openButtons.forEach((button) => button.addEventListener("click", openModal));
  closeButtons.forEach((button) => button.addEventListener("click", closeModal));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
})();
