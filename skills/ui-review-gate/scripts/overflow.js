/* ui-review-gate overflow snippet. One expression: pass the whole file to the host's page-evaluation tool.
   Read-only: no network, no storage, no navigation, no DOM change. Returns a JSON string.
   Reports whether the document scrolls sideways at the current width, the outermost elements that reach past
   the viewport, and the regions that scroll sideways inside themselves (allowed only for content that needs a
   two-dimensional layout: data tables, maps, diagrams, toolbars, video; the report names each one). */
(() => {
  const LIMIT = 50;
  const root = document.documentElement;
  const viewport = root.clientWidth;
  const scrolls = (el) => {
    const s = getComputedStyle(el);
    return /^(auto|scroll)$/.test(s.overflowX) || /^(auto|scroll)$/.test(s.overflow);
  };
  const insideRegion = (el) => {
    for (let n = el.parentElement; n && n !== root; n = n.parentElement) if (scrolls(n)) return true;
    return false;
  };
  const describe = (el) => ({ tag: el.tagName.toLowerCase(), id: el.getAttribute("id") || null,
    class: (el.getAttribute("class") || "").slice(0, 60) || null });
  const culprits = [];
  const regions = [];
  const seen = new Set();
  for (const el of Array.from(document.querySelectorAll("body *"))) {
    const s = getComputedStyle(el);
    if (s.display === "none") continue;
    const r = el.getBoundingClientRect();
    if (scrolls(el) && el.scrollWidth > el.clientWidth && regions.length < LIMIT) {
      regions.push({ ...describe(el), scrollWidth: el.scrollWidth, clientWidth: el.clientWidth });
    }
    if (insideRegion(el) || r.width <= 0) continue;
    const past = r.left + r.width > viewport + 0.5 || r.left < -0.5;
    if (!past) continue;
    let parent = el.parentElement;
    let nested = false;
    for (; parent; parent = parent.parentElement) if (seen.has(parent)) { nested = true; break; }
    seen.add(el);
    if (!nested && culprits.length < LIMIT) {
      culprits.push({ ...describe(el), left: Math.round(r.left), right: Math.round(r.left + r.width),
        width: Math.round(r.width), position: s.position });
    }
  }
  return JSON.stringify({ snippet: "overflow", viewport, scrollWidth: root.scrollWidth,
    horizontalScroll: root.scrollWidth > viewport, culprits, scrollRegions: regions });
})()
