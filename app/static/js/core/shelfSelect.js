// Custom pick list — stays inside its container, ellipsis on long labels, scrollable panel.
import { el, esc } from "./dom.js";

const ROW_PX = 40;

export function mountPickSelect(container, {
  name = "value",
  placeholder = "— select —",
  visibleRows = 6,
} = {}) {
  const hidden = el("input");
  hidden.type = "hidden";
  hidden.name = name;

  const wrap = el("div", "pick-select");
  wrap.style.setProperty("--pick-visible-rows", String(visibleRows));
  const trigger = el("button", "pick-select-trigger", placeholder);
  trigger.type = "button";
  const panel = el("div", "pick-select-panel hidden");
  const list = el("div", "pick-select-list");
  const more = el("div", "pick-select-more hidden", "▼");
  panel.append(list, more);
  wrap.append(trigger, panel);
  container.append(wrap, hidden);

  let options = [];
  let onDocClick = null;
  let changeHandler = null;
  let emptyLabel = placeholder;

  function updateMore() {
    const hasOverflow = list.scrollHeight > list.clientHeight + 1;
    const atBottom = list.scrollTop + list.clientHeight >= list.scrollHeight - 2;
    more.classList.toggle("hidden", !hasOverflow || atBottom);
  }

  function renderOptions() {
    list.innerHTML = "";
    for (const opt of options) {
      const row = el("div", "pick-select-option", esc(opt.label));
      row.title = opt.label;
      row.dataset.value = opt.value;
      if (String(opt.value) === String(hidden.value)) row.classList.add("active");
      row.onclick = () => {
        setValue(opt.value);
        close();
      };
      list.appendChild(row);
    }
    list.scrollTop = 0;
    requestAnimationFrame(updateMore);
  }

  function syncTrigger() {
    const found = options.find((o) => String(o.value) === String(hidden.value));
    trigger.textContent = found ? found.label : emptyLabel;
    list.querySelectorAll(".pick-select-option").forEach((row) => {
      row.classList.toggle("active", row.dataset.value === String(hidden.value));
    });
  }

  function setValue(val) {
    const prev = hidden.value;
    hidden.value = val ?? "";
    syncTrigger();
    if (String(prev) !== String(hidden.value)) changeHandler?.();
  }

  function open() {
    if (trigger.disabled) return;
    panel.classList.remove("hidden");
    wrap.classList.add("open");
    list.scrollTop = 0;
    const rect = trigger.getBoundingClientRect();
    const panelH = visibleRows * ROW_PX;
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    wrap.classList.toggle("open-up", spaceBelow < panelH && spaceAbove > spaceBelow);
    requestAnimationFrame(updateMore);
    onDocClick = (e) => {
      if (!wrap.contains(e.target)) close();
    };
    setTimeout(() => document.addEventListener("click", onDocClick), 0);
  }

  function close() {
    panel.classList.add("hidden");
    wrap.classList.remove("open", "open-up");
    if (onDocClick) {
      document.removeEventListener("click", onDocClick);
      onDocClick = null;
    }
  }

  trigger.onclick = (e) => {
    e.stopPropagation();
    if (panel.classList.contains("hidden")) open();
    else close();
  };

  list.addEventListener("scroll", updateMore);

  return {
    root: wrap,
    setOptions(entries, nextPlaceholder) {
      if (nextPlaceholder) emptyLabel = nextPlaceholder;
      options = entries.map((entry) => {
        if (Array.isArray(entry)) return { value: entry[0], label: entry[1] };
        return entry;
      });
      renderOptions();
      syncTrigger();
    },
    setValue,
    getValue: () => hidden.value,
    setDisabled(disabled) {
      trigger.disabled = !!disabled;
      wrap.classList.toggle("disabled", !!disabled);
      if (disabled) close();
    },
    onChange(fn) {
      changeHandler = fn;
    },
    reset() {
      hidden.value = "";
      trigger.textContent = emptyLabel;
      list.innerHTML = "";
      more.classList.add("hidden");
      close();
    },
  };
}

export function mountShelfSelect(container) {
  const picker = mountPickSelect(container, {
    name: "shelf_id",
    placeholder: "— select bay —",
    visibleRows: 6,
  });
  return {
    setOptions(entries) { picker.setOptions(entries); },
    setValue: (v) => picker.setValue(v),
    getValue: () => picker.getValue(),
    onChange: (fn) => picker.onChange(fn),
    reset: () => picker.reset(),
  };
}
