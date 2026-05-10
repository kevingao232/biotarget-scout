const form = document.getElementById("form");
const out = document.getElementById("out");
const statusEl = document.getElementById("status");
const btn = document.getElementById("btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const query = (fd.get("query") || "").toString().trim();
  const body = {
    query,
    index_mode: fd.get("index_mode"),
    leg_retries: Number(fd.get("leg_retries") || 2),
  };

  out.hidden = true;
  statusEl.textContent = "Running…";
  btn.disabled = true;

  try {
    const res = await fetch("/api/v1/hypothesis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
    if (!res.ok) {
      statusEl.textContent = `Error ${res.status}`;
      out.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
      out.hidden = false;
      return;
    }
    statusEl.textContent = "Done.";
    out.textContent = JSON.stringify(data, null, 2);
    out.hidden = false;
  } catch (err) {
    statusEl.textContent = "Network error";
    out.textContent = String(err);
    out.hidden = false;
  } finally {
    btn.disabled = false;
  }
});
