/* ui-review-gate form-fields snippet. One expression: pass the whole file to the host's page-evaluation tool.
   Read-only: no network, no storage, no navigation, no DOM change. Returns a JSON string.
   Lists the form fields in document order with name, type, inputmode, autocomplete, label and required state.
   It never reads a field's value, so no entered data enters the evidence; the ordered names prove the
   "field order unchanged" constraint before and after a fix. */
(() => {
  const SKIP = /^(hidden|submit|button|reset|image)$/;
  const all = Array.from(document.querySelectorAll("*"));
  const text = (el) => (el ? (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80) : "");
  const byId = (id) => all.find((n) => n.getAttribute("id") === id) || null;
  const label = (el) => {
    const ids = (el.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
    if (ids.length) {
      const joined = ids.map((id) => text(byId(id))).filter(Boolean).join(" ");
      if (joined) return { label: joined, source: "aria-labelledby" };
    }
    if (el.getAttribute("aria-label")) return { label: el.getAttribute("aria-label").trim(), source: "aria-label" };
    const id = el.getAttribute("id");
    if (id) {
      const own = all.find((n) => n.tagName.toLowerCase() === "label" && n.getAttribute("for") === id);
      if (own && text(own)) return { label: text(own), source: "label-for" };
    }
    for (let n = el.parentElement; n; n = n.parentElement) {
      if (n.tagName.toLowerCase() === "label" && text(n)) return { label: text(n), source: "label-wrap" };
    }
    if (el.getAttribute("placeholder")) return { label: el.getAttribute("placeholder"), source: "placeholder-only" };
    if (el.getAttribute("title")) return { label: el.getAttribute("title"), source: "title-only" };
    return { label: null, source: "none" };
  };
  const forms = all.filter((n) => n.tagName.toLowerCase() === "form");
  const formOf = (el) => {
    const owner = el.getAttribute("form");
    if (owner) return forms.findIndex((f) => f.getAttribute("id") === owner);
    for (let n = el.parentElement; n; n = n.parentElement) if (n.tagName.toLowerCase() === "form") return forms.indexOf(n);
    return -1;
  };
  const fields = [];
  for (const el of all) {
    const tag = el.tagName.toLowerCase();
    if (!/^(input|select|textarea)$/.test(tag)) continue;
    const type = tag === "input" ? (el.getAttribute("type") || "text").toLowerCase() : tag;
    if (tag === "input" && SKIP.test(type)) continue;
    const named = label(el);
    fields.push({ order: fields.length + 1, form: formOf(el), tag, name: el.getAttribute("name") || null,
      id: el.getAttribute("id") || null, type, inputmode: el.getAttribute("inputmode") || null,
      autocomplete: el.getAttribute("autocomplete") || null, label: named.label, labelSource: named.source,
      required: el.hasAttribute("required") || el.getAttribute("aria-required") === "true",
      invalid: el.getAttribute("aria-invalid") === "true",
      describedBy: !!el.getAttribute("aria-describedby"), disabled: el.hasAttribute("disabled") });
  }
  return JSON.stringify({ snippet: "fields", forms: forms.map((f, i) => ({ index: i, id: f.getAttribute("id") || null,
    name: f.getAttribute("name") || null, noValidate: f.hasAttribute("novalidate") })),
  order: fields.map((f) => f.name || f.id || "(unnamed)"), fields });
})()
