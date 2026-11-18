/* ui-review-gate target-size snippet. One expression: pass the whole file to the host's page-evaluation tool.
   Read-only: no network, no storage, no navigation, no DOM change. Returns a JSON string.
   WCAG 2.2 AA 2.5.8: a target below 24 by 24 CSS px is blocking unless the spacing exception (a 24 px circle
   centred on it meets no other target and no other undersized target's circle) or the inline exception
   (a link inside a line of text) applies. 24 to 43 px is low: 44 px is Apple's guideline and WCAG AAA 2.5.5. */
(() => {
  const LIMIT = 300;
  const ROLES = /^(button|link|checkbox|radio|switch|tab|menuitem|menuitemcheckbox|menuitemradio|option|slider|spinbutton)$/;
  const interactive = (el) => {
    const tag = el.tagName.toLowerCase();
    if (el.hasAttribute("disabled")) return false;
    if (tag === "a") return el.hasAttribute("href");
    if (tag === "input") return (el.getAttribute("type") || "").toLowerCase() !== "hidden";
    if (/^(button|select|textarea|summary)$/.test(tag)) return true;
    if (ROLES.test(el.getAttribute("role") || "")) return true;
    const tabindex = el.getAttribute("tabindex");
    return tabindex !== null && parseInt(tabindex, 10) >= 0;
  };
  const visible = (el, rect) => {
    if (rect.width <= 0 || rect.height <= 0) return false;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === "none" || s.visibility === "hidden") return false;
    }
    return true;
  };
  const sizeClass = (w, h) => (Math.min(w, h) < 24 ? "below-24" : Math.min(w, h) < 44 ? "24-43" : "44-plus");
  const centre = (r) => [r.left + r.width / 2, r.top + r.height / 2];
  const circleMeetsRect = (c, r) => {
    const dx = c[0] - Math.max(r.left, Math.min(c[0], r.left + r.width));
    const dy = c[1] - Math.max(r.top, Math.min(c[1], r.top + r.height));
    return dx * dx + dy * dy < 144;
  };
  const circlesMeet = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < 576;
  const inline = (el) => {
    /* A link in a sentence: climb inline wrappers (a span around the link) to the first block, and look for
       text there outside the link itself. */
    if (el.tagName.toLowerCase() !== "a" || getComputedStyle(el).display !== "inline") return false;
    let n = el;
    while (n.parentElement && getComputedStyle(n.parentElement).display === "inline") n = n.parentElement;
    const block = n.parentElement;
    if (!block) return false;
    const walk = (node) => {
      if (node === el) return false;
      if (node.nodeType === 3) return !!node.textContent.trim();
      return Array.from(node.childNodes || []).some(walk);
    };
    return Array.from(block.childNodes).some(walk);
  };
  const describe = (el) => {
    const text = (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40);
    return { tag: el.tagName.toLowerCase(), id: el.getAttribute("id") || null, name: el.getAttribute("name") || null,
      label: el.getAttribute("aria-label") || text || null };
  };
  const targets = [];
  for (const el of Array.from(document.querySelectorAll("*"))) {
    if (!interactive(el)) continue;
    const r = el.getBoundingClientRect();
    if (!visible(el, r)) continue;
    targets.push({ el, rect: { left: r.left, top: r.top, width: r.width, height: r.height } });
  }
  const small = targets.filter((t) => sizeClass(t.rect.width, t.rect.height) === "below-24");
  const results = [];
  for (const t of targets) {
    const size = sizeClass(t.rect.width, t.rect.height);
    if (size === "44-plus") continue;
    const entry = { ...describe(t.el), width: Math.round(t.rect.width * 10) / 10,
      height: Math.round(t.rect.height * 10) / 10, size, exception: null };
    const type = (t.el.getAttribute("type") || "").toLowerCase();
    if (t.el.tagName.toLowerCase() === "input" && /^(checkbox|radio)$/.test(type)) {
      entry.uncertain = true;
      entry.note = "a label that activates this control may count toward its target: check by eye";
    }
    if (size === "below-24") {
      const c = centre(t.rect);
      const spaced = targets.every((o) => o === t || !circleMeetsRect(c, o.rect))
        && small.every((o) => o === t || !circlesMeet(c, centre(o.rect)));
      if (inline(t.el)) entry.exception = "inline";
      else if (spaced) entry.exception = "spacing";
      entry.severity = entry.exception ? "low" : "blocking";
      entry.criterion = "2.5.8";
    } else {
      entry.severity = "low";
      entry.criterion = "2.5.5 (AAA) and Apple's 44 px guideline";
    }
    results.push(entry);
    if (results.length >= LIMIT) break;
  }
  return JSON.stringify({ snippet: "targets", checked: targets.length, truncated: results.length >= LIMIT,
    blocking: results.filter((r) => r.severity === "blocking").length,
    low: results.filter((r) => r.severity === "low").length, results });
})()
