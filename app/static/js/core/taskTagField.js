// Task tags — type text, press Enter to add; multiple tags stored comma-separated in note.

function normalizeTag(raw) {
  return String(raw || "").trim().replace(/^[,;.\s]+|[,;.\s]+$/g, "");
}

export function splitTaskTags(note) {
  return String(note || "")
    .split(",")
    .map(normalizeTag)
    .filter(Boolean);
}

export function joinTaskTags(tags) {
  return tags.map(normalizeTag).filter(Boolean).join(", ");
}

function parts(root) {
  if (!root) return null;
  let chipsEl = root.querySelector(".task-tag-chips");
  if (!chipsEl) {
    chipsEl = document.createElement("div");
    chipsEl.className = "task-tag-chips";
    const typeEl = root.querySelector(".task-tag-type");
    root.insertBefore(chipsEl, typeEl || root.firstChild);
  }
  return {
    root,
    chipsEl,
    typeEl: root.querySelector(".task-tag-type"),
    hiddenEl: root.querySelector('input[type="hidden"][name="note"]'),
  };
}

function renderChips(p, tags) {
  p.chipsEl.innerHTML = "";
  tags.forEach((tag, index) => {
    const chip = document.createElement("span");
    chip.className = "task-tag task-tag-chip";
    chip.innerHTML = `<span class="task-tag-lbl">TAG</span><span class="task-tag-val"></span>`;
    chip.querySelector(".task-tag-val").textContent = tag;
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "task-tag-clear";
    clearBtn.setAttribute("aria-label", `Remove tag ${tag}`);
    clearBtn.textContent = "×";
    clearBtn.addEventListener("click", () => {
      const next = tags.filter((_, i) => i !== index);
      syncTags(p, next);
      p.typeEl?.focus();
    });
    chip.appendChild(clearBtn);
    p.chipsEl.appendChild(chip);
  });
  p.hiddenEl.value = joinTaskTags(tags);
}

function syncTags(p, tags) {
  renderChips(p, tags);
}

function currentTags(p) {
  return splitTaskTags(p.hiddenEl.value);
}

function addTag(p, raw) {
  const value = normalizeTag(raw);
  if (!value) return currentTags(p);
  const tags = currentTags(p);
  if (tags.some((t) => t.toLowerCase() === value.toLowerCase())) return tags;
  tags.push(value);
  syncTags(p, tags);
  return tags;
}

export function setTaskTagValue(root, value) {
  const p = parts(root);
  if (!p) return;
  syncTags(p, splitTaskTags(value));
  p.typeEl.value = "";
  p.typeEl.classList.remove("hidden");
}

export function commitTaskTag(root) {
  const p = parts(root);
  if (!p) return "";
  const pending = normalizeTag(p.typeEl.value);
  if (pending) addTag(p, pending);
  p.typeEl.value = "";
  return p.hiddenEl.value;
}

export function wireTaskTagField(root) {
  const p = parts(root);
  if (!p || p.root.dataset.tagWired) return;
  p.root.dataset.tagWired = "1";

  const commitTyped = () => {
    const pending = normalizeTag(p.typeEl.value);
    if (!pending) return;
    addTag(p, pending);
    p.typeEl.value = "";
  };

  p.typeEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      commitTyped();
    }
    if (e.key === "Backspace" && !p.typeEl.value && currentTags(p).length) {
      const tags = currentTags(p);
      tags.pop();
      syncTags(p, tags);
    }
  });
  p.typeEl.addEventListener("blur", commitTyped);

  p.root.closest("form")?.addEventListener("reset", () => {
    setTimeout(() => setTaskTagValue(p.root, p.hiddenEl.value || ""), 0);
  });
}

export function taskTagsHtml(note, esc) {
  const tags = splitTaskTags(note);
  if (!tags.length) return "";
  const safe = esc || ((s) => s);
  return tags
    .map((t) => `<span class="task-tag"><span class="task-tag-lbl">TAG</span>${safe(t)}</span>`)
    .join("");
}
