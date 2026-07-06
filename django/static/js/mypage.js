(() => {
  document.querySelectorAll(".game-progress").forEach((bar) => {
    const current = Number(bar.dataset.current || 0);
    const target = Number(bar.dataset.target || 0);
    const percent = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
    const fill = bar.querySelector("span");
    if (fill) fill.style.width = `${percent}%`;
  });

  document.querySelectorAll(".mp-progress-ring").forEach((ring) => {
    const progress = Math.max(0, Math.min(100, Number(ring.dataset.progress || 0)));
    const degrees = Math.round((progress / 100) * 360);
    ring.style.background = `conic-gradient(var(--g-green) 0deg ${degrees}deg, rgba(255,255,255,0.08) ${degrees}deg 360deg)`;
  });
})();
