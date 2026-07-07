// ACCOUNT_SETTINGS_V51_RESTORE
// ACCOUNT_SETTINGS_V48: 마이페이지 회원 정보 수정 팝업
(() => {
  const modal = document.getElementById("accountSettingsModal");
  if (!modal) return;

  const openButtons = document.querySelectorAll("[data-account-modal-open]");
  const closeButtons = document.querySelectorAll("[data-account-modal-close]");
  const firstInput = modal.querySelector("input[name='username']");

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    window.setTimeout(() => firstInput?.focus(), 40);
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
  };

  openButtons.forEach((button) => button.addEventListener("click", openModal));
  closeButtons.forEach((button) => button.addEventListener("click", closeModal));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
})();
