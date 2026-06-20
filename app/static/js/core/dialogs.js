// Centered prompt/confirm dialogs (replace the browser's native ones).
import { $ } from "./dom.js";

export function askPrompt(title, label, placeholder = "", defaultValue = "", refreshFn = null) {
  return new Promise((resolve) => {
    $("#prompt-title").textContent = title;
    $("#prompt-label").textContent = label;
    const inp = $("#prompt-input");
    const refreshBtn = $("#prompt-refresh");
    inp.value = defaultValue;
    inp.placeholder = placeholder;
    if (refreshFn) {
      refreshBtn.classList.remove("hidden");
      refreshBtn.onclick = (e) => {
        e.preventDefault();
        inp.value = refreshFn();
        inp.focus();
        inp.select();
      };
    } else {
      refreshBtn.classList.add("hidden");
      refreshBtn.onclick = null;
    }
    $("#prompt-modal").classList.remove("hidden");
    setTimeout(() => { inp.focus(); inp.select(); }, 30);
    const done = (val) => {
      $("#prompt-form").onsubmit = null;
      $("#prompt-cancel").onclick = null;
      $("#prompt-close").onclick = null;
      refreshBtn.onclick = null;
      refreshBtn.classList.add("hidden");
      $("#prompt-modal").classList.add("hidden");
      resolve(val);
    };
    $("#prompt-form").onsubmit = (e) => { e.preventDefault(); done(inp.value.trim() || null); };
    $("#prompt-cancel").onclick = () => done(null);
    $("#prompt-close").onclick = () => done(null);
  });
}

export function askConfirm(message, title = "Confirm") {
  return new Promise((resolve) => {
    $("#confirm-title").textContent = title;
    $("#confirm-msg").textContent = message;
    $("#confirm-modal").classList.remove("hidden");
    const done = (val) => {
      $("#confirm-yes").onclick = null; $("#confirm-no").onclick = null;
      $("#confirm-modal").classList.add("hidden");
      resolve(val);
    };
    $("#confirm-yes").onclick = () => done(true);
    $("#confirm-no").onclick = () => done(false);
  });
}
