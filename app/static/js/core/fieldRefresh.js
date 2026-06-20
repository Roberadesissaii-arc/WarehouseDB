/** Wire an input + refresh button (inline, beside the field). */
export function wireFieldRefresh(input, refreshBtn, fill) {
  const run = () => {
    if (!input) return;
    fill();
    input.focus();
    input.select();
  };
  refreshBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    run();
  });
  return run;
}
