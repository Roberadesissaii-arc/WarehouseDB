// Browser push notifications (desktop + phone) — permission is per device; prefs are per platform.
const MOBILE_MQ = window.matchMedia("(max-width: 640px)");

export function isMobileDevice() {
  return MOBILE_MQ.matches || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

export function pushNotificationsSupported() {
  return typeof window !== "undefined" && "Notification" in window;
}

export function pushNeedsSecureContext() {
  return pushNotificationsSupported() && !window.isSecureContext;
}

export function pushPermission() {
  if (!pushNotificationsSupported()) return "unsupported";
  if (pushNeedsSecureContext()) return "insecure";
  return Notification.permission;
}

export async function requestPushPermission() {
  if (!pushNotificationsSupported()) return "unsupported";
  if (pushNeedsSecureContext()) return "insecure";
  if (Notification.permission === "granted") return "granted";
  if (Notification.permission === "denied") return "denied";
  try {
    return await Notification.requestPermission();
  } catch {
    return "denied";
  }
}

export function permissionStatusText(perm = pushPermission()) {
  if (perm === "unsupported") return "This browser does not support notifications.";
  if (perm === "insecure") {
    return "Notifications need HTTPS or localhost. Open WarehouseDB with https:// or use localhost on this machine.";
  }
  if (perm === "granted") return "Browser permission granted on this device.";
  if (perm === "denied") {
    return "Blocked by the browser — open site settings for this address and allow notifications, then try again.";
  }
  return "Not enabled yet — turn on below and allow when the browser asks.";
}

export function showPushNotification(title, body, tag = "wdb-test") {
  if (!pushNotificationsSupported() || pushPermission() !== "granted") return false;
  try {
    new Notification(title || "WarehouseDB alert", {
      body: body || "",
      tag,
      icon: "/static/icons/apple-touch-icon.png",
    });
    return true;
  } catch {
    return false;
  }
}

export async function enablePushForPlatform(_platform, { onStatus } = {}) {
  const perm = await requestPushPermission();
  onStatus?.(perm);
  if (perm === "granted") return { ok: true, permission: perm };
  if (perm === "insecure") {
    return { ok: false, permission: perm, message: permissionStatusText("insecure") };
  }
  if (perm === "denied") {
    return { ok: false, permission: perm, message: permissionStatusText("denied") };
  }
  if (perm === "unsupported") {
    return { ok: false, permission: perm, message: permissionStatusText("unsupported") };
  }
  return { ok: false, permission: perm, message: "Notification permission was not granted." };
}
