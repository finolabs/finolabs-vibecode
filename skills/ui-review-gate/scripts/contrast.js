/* ui-review-gate contrast snippet. One expression: pass the whole file to the host's page-evaluation tool.
   Read-only: no network, no storage, no navigation, no DOM change. Returns a JSON string.
   Text: 4.5:1 for normal text, 3:1 for large text (WCAG 2.2 1.4.3). UI components: 3:1 for the visual
   boundary of a control against what is behind it (1.4.11). A background image, a gradient, a colour the
   snippet cannot parse or a reading through opacity is marked uncertain: check it by eye. */
(() => {
  const LIMIT = 200;
  const parse = (value) => {
    if (typeof value !== "string") return null;
    const v = value.trim().toLowerCase();
    if (v === "transparent") return [0, 0, 0, 0];
    let m = v.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/);
    if (!m) m = v.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+%?))?\s*\)$/);
    if (!m) return null;
    const scale = v.startsWith("color(") ? 255 : 1;
    const alpha = m[4] === undefined ? 1 : m[4].endsWith("%") ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return [parseFloat(m[1]) * scale, parseFloat(m[2]) * scale, parseFloat(m[3]) * scale, alpha];
  };
  const over = (top, under) => {
    const a = top[3];
    return [0, 1, 2].map((i) => top[i] * a + under[i] * (1 - a)).concat(1);
  };
  const channel = (c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const luminance = (rgb) => 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2]);
  const ratio = (a, b) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100;
  };
  const isLarge = (style) => {
    const size = parseFloat(style.fontSize) || 16;
    const weight = parseInt(style.fontWeight, 10) || (style.fontWeight === "bold" ? 700 : 400);
    return size >= 24 || (size >= 18.66 && weight >= 700);
  };
  const hidden = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === "none" || s.visibility === "hidden" || parseFloat(s.opacity) === 0) return true;
    }
    return false;
  };
  const backdrop = (el) => {
    let colour = [0, 0, 0, 0];
    let uncertain = false;
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage && s.backgroundImage !== "none") uncertain = true;
      if (parseFloat(s.opacity) < 1) uncertain = true;
      const c = parse(s.backgroundColor);
      if (!c) { uncertain = true; continue; }
      layers.push(c);
      if (c[3] >= 1) break;
    }
    layers.push([255, 255, 255, 1]);
    for (let i = layers.length - 1; i >= 0; i -= 1) colour = over(layers[i], colour);
    return { colour, uncertain };
  };
  const describe = (el) => {
    const id = el.getAttribute("id");
    const name = el.getAttribute("name");
    const text = (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40);
    return { tag: el.tagName.toLowerCase(), id: id || null, name: name || null, text };
  };
  const hex = (c) => "#" + c.slice(0, 3).map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");
  const CONTROL = /^(button|input|select|textarea)$/;
  const ROLES = /^(button|checkbox|radio|switch|tab|textbox|combobox|slider)$/;
  const results = [];
  let checked = 0;
  for (const el of Array.from(document.querySelectorAll("*"))) {
    if (results.length >= LIMIT) break;
    const tag = el.tagName.toLowerCase();
    if (/^(html|head|script|style|meta|link|title|noscript|template)$/.test(tag) || hidden(el)) continue;
    const style = getComputedStyle(el);
    const ownText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
    if (ownText) {
      checked += 1;
      const fg = parse(style.color);
      const back = backdrop(el);
      if (!fg) { results.push({ kind: "text", ...describe(el), uncertain: true, reason: "colour not parsed" }); continue; }
      const shown = over(fg, back.colour);
      const r = ratio(shown, back.colour);
      const large = isLarge(style);
      const threshold = large ? 3 : 4.5;
      results.push({ kind: "text", ...describe(el), large, ratio: r, threshold, pass: r >= threshold,
        foreground: hex(shown), background: hex(back.colour), uncertain: back.uncertain || fg[3] < 1 });
    }
    if (CONTROL.test(tag) || ROLES.test(el.getAttribute("role") || "")) {
      if (tag === "input" && /^(hidden)$/.test((el.getAttribute("type") || "").toLowerCase())) continue;
      checked += 1;
      const behind = backdrop(el.parentElement || el);
      const border = parseFloat(style.borderTopWidth) > 0 ? parse(style.borderTopColor) : null;
      const fill = parse(style.backgroundColor);
      let edge = null;
      let source = null;
      if (border && border[3] > 0) { edge = over(border, behind.colour); source = "border"; }
      else if (fill && fill[3] > 0) { edge = over(fill, behind.colour); source = "background"; }
      if (!edge) {
        results.push({ kind: "component", ...describe(el), boundary: null, threshold: 3, pass: null,
          uncertain: true, reason: "no border or fill: check the visual boundary by eye" });
        continue;
      }
      const r = ratio(edge, behind.colour);
      results.push({ kind: "component", ...describe(el), boundary: source, ratio: r, threshold: 3, pass: r >= 3,
        foreground: hex(edge), background: hex(behind.colour), uncertain: behind.uncertain });
    }
  }
  return JSON.stringify({ snippet: "contrast", checked, truncated: results.length >= LIMIT,
    failures: results.filter((r) => r.pass === false).length, results });
})()
