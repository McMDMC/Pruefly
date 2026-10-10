"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const TYPE_DE = {
    eq_grid: "Rechenaufgaben", table_vn: "Vorgänger/Nachfolger", alphabet_errors: "Alphabet-Fehler",
    word_sort: "Wörter ordnen", chain: "Rechenkette", number_line: "Zahlenstrahl", measure: "Messen",
    draw_lines: "Linien zeichnen", shapes: "Formen zählen", info_box: "Merkkasten",
    gap_text: "Lückentext", text: "Text",
  };
  let code = "";
  try { code = sessionStorage.getItem("pruefly_code") || ""; } catch (_) { /* private mode */ }
  let ir = null;        // the original, as recognised
  let variant = null;   // the current generated variant

  const show = (...ids) => ["login", "step1", "step2", "step3"].forEach((s) => ($(s).hidden = !ids.includes(s)));
  const setErr = (id, msg) => { $(id).textContent = msg || ""; };

  async function api(path, body, wantBlob) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Access-Code": code },
      body: JSON.stringify(body || {}),
    });
    if (res.status === 401) { show("login"); throw new Error("Zugangscode falsch oder fehlt."); }
    if (!res.ok) {
      let msg = "Fehler " + res.status;
      try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch (_) {}
      throw new Error(msg);
    }
    return wantBlob ? res.blob() : res.json();
  }

  // Resize to max 1568px JPEG: smaller upload, faster, and strips EXIF/location.
  function toJpegBase64(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const max = 1568, k = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement("canvas");
        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        resolve(c.toDataURL("image/jpeg", 0.85).split(",")[1]);
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Bild konnte nicht geladen werden.")); };
      img.src = url;
    });
  }

  function renderSummary(rep, title) {
    $("title2").textContent = title || "Arbeitsblatt";
    const ul = $("tasks2"); ul.textContent = "";
    rep.tasks.forEach((t, i) => {
      const li = document.createElement("li");
      let txt = `${i + 1}. ${TYPE_DE[t.type] || t.type}`;
      if (t.items != null) txt += ` – ${t.items} ${t.type === "word_sort" ? "Wörter" : t.type === "gap_text" ? "Sätze" : "Aufgaben"}`;
      if (t.solvable != null && t.solvable < t.items) txt += ` (${t.solvable} lösbar erkannt)`;
      if (!t.regenerable) txt += " – bleibt unverändert";
      li.textContent = txt; ul.appendChild(li);
    });
    const w = $("warn2"); w.textContent = "";
    (rep.warnings || []).forEach((m) => { const li = document.createElement("li"); li.textContent = m; w.appendChild(li); });
  }

  async function preview() {
    setErr("err3");
    try {
      const r = await api("/api/render", { ir: variant, format: "html", solution: $("sol").checked });
      const f = $("preview");
      f.srcdoc = r.html;
      f.onload = () => {
        try { f.style.height = Math.min(1400, f.contentDocument.documentElement.scrollHeight + 8) + "px"; } catch (_) {}
      };
    } catch (e) { setErr("err3", e.message); }
  }

  async function generate() {
    setErr("err2"); setErr("err3");
    $("gen").disabled = $("reroll").disabled = true; $("busy2").hidden = false;
    try {
      const r = await api("/api/transform", { ir });
      variant = r.ir;
      (r.warnings || []).forEach((m) => { const li = document.createElement("li"); li.textContent = m; $("warn2").appendChild(li); });
      show("step2", "step3");
      await preview();
      $("step3").scrollIntoView({ behavior: "smooth" });
    } catch (e) { setErr("err2", e.message); }
    finally { $("gen").disabled = $("reroll").disabled = false; $("busy2").hidden = true; }
  }

  async function download(solution) {
    setErr("err3");
    try {
      const blob = await api("/api/render", { ir: variant, format: "pdf", solution }, true);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (solution ? "Loesung_" : "Arbeitsblatt_") + new Date().toISOString().slice(0, 10) + ".pdf";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    } catch (e) { setErr("err3", e.message); }
  }

  $("login-form").addEventListener("submit", async (ev) => {
    ev.preventDefault(); setErr("login-err");
    code = $("code").value;
    try {
      await api("/api/check");
      try { sessionStorage.setItem("pruefly_code", code); } catch (_) {}
      show(ir ? "step2" : "step1");
    } catch (e) { setErr("login-err", e.message); }
  });

  $("photo").addEventListener("change", async (ev) => {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    setErr("err1"); $("busy1").hidden = false;
    try {
      const b64 = await toJpegBase64(file);
      const r = await api("/api/analyze", { image_b64: b64 });
      ir = r.ir; variant = null;
      renderSummary(r.report, r.ir.title);
      show("step2");
    } catch (e) { setErr("err1", e.message); }
    finally { $("busy1").hidden = true; ev.target.value = ""; }
  });

  $("gen").addEventListener("click", generate);
  $("reroll").addEventListener("click", generate);
  $("again").addEventListener("click", () => { ir = variant = null; show("step1"); });
  $("sol").addEventListener("change", preview);
  $("pdf").addEventListener("click", () => download(false));
  $("pdfsol").addEventListener("click", () => download(true));

  (async () => {
    try {
      const cfg = await (await fetch("/api/config")).json();
      if (!cfg.configured) { show("login"); setErr("login-err", "Server nicht konfiguriert (Zugangscode fehlt)."); return; }
      if (cfg.auth_required && !code) { show("login"); return; }
      show("step1");
    } catch (_) { show("step1"); }
  })();
})();
