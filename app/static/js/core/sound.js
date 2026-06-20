// Notification sounds, synthesized with the Web Audio API (no audio files).
// Also handles optional browser push notifications. Preferences come from /api/settings.

import { isMobileDevice, pushPermission, showPushNotification } from "./pushNotifications.js";

// pattern = [frequency Hz, startOffset s, duration s, waveform?]
export const PATTERNS = {
  chime: [[880, 0, 0.14], [1318.5, 0.12, 0.22]],
  beep: [[660, 0, 0.1], [660, 0.16, 0.12]],
  ding: [[1244.5, 0, 0.5, "triangle"]],
  alert: [[740, 0, 0.12], [740, 0.18, 0.12], [988, 0.36, 0.18]],
};

let prefs = {
  sound: true,
  kind: "chime",
  volume: 0.7,
  desktop: false,
  mobile: false,
  kinds: { fleet: true, store: true, system: true },
};
let ctx = null;
let unlocked = false;

function ensureCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  return ctx;
}

// Browsers block audio until a user gesture — unlock on the first interaction.
export function unlockAudio() {
  const c = ensureCtx();
  if (c && c.state === "suspended") c.resume();
  unlocked = true;
}
function armUnlock() {
  const handler = () => { unlockAudio(); document.removeEventListener("pointerdown", handler); document.removeEventListener("keydown", handler); };
  document.addEventListener("pointerdown", handler);
  document.addEventListener("keydown", handler);
}
armUnlock();

export function playSound(kind = prefs.kind, volume = prefs.volume) {
  const c = ensureCtx();
  if (!c) return;
  if (c.state === "suspended") c.resume();
  const pattern = PATTERNS[kind] || PATTERNS.chime;
  const now = c.currentTime;
  const vol = Math.max(0, Math.min(1, volume));
  for (const [freq, start, dur, wave] of pattern) {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = wave || "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, now + start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.001, vol), now + start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
    osc.connect(gain).connect(c.destination);
    osc.start(now + start);
    osc.stop(now + start + dur + 0.03);
  }
}

// Fired by the notifications feed when a genuinely new alert arrives.
export function alertSound(kind) {
  if (!prefs.sound) return;
  if (kind && prefs.kinds && prefs.kinds[kind] === false) return;
  try { playSound(prefs.kind, prefs.volume); } catch { /* ignore */ }
}

export function maybeDesktop(notif) {
  if (!notif) return;
  const enabled = isMobileDevice() ? prefs.mobile : prefs.desktop;
  if (!enabled) return;
  if (pushPermission() !== "granted") return;
  if (notif.kind && prefs.kinds && prefs.kinds[notif.kind] === false) return;
  showPushNotification(
    notif.title || "WarehouseDB alert",
    notif.body || "",
    `wdb-${notif.id || Date.now()}`,
  );
}

export function applyPrefs(n) {
  if (!n) return;
  prefs = {
    sound: n.sound !== false,
    kind: n.sound_kind || "chime",
    volume: Math.max(0, Math.min(1, (Number(n.volume) || 70) / 100)),
    desktop: !!n.desktop,
    mobile: !!n.mobile,
    kinds: n.kinds || prefs.kinds,
  };
}

export async function loadSoundPrefs() {
  try {
    const r = await fetch("/api/settings");
    if (!r.ok) return;
    const s = await r.json();
    if (s && s.notifications) applyPrefs(s.notifications);
  } catch { /* ignore */ }
}
