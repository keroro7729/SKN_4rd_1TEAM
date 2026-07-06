// mypage interaction hook for future charts/progress animations.
document.querySelectorAll('.progress-bar span').forEach((bar) => {
  const width = bar.style.width || '0%';
  bar.style.width = '0%';
  requestAnimationFrame(() => { bar.style.width = width; });
});
