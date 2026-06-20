// Thin fetch wrapper. Redirects to /login on 401.
export const api = {
  async get(url) {
    const r = await fetch(url);
    if (r.status === 401) { location.href = "/login"; return; }
    return r.json();
  },
  async send(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) { location.href = "/login"; return; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
  },
};
