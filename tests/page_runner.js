/* Runs the script of skills/fnl-status/assets/dashboard.html against a small fake DOM and prints the rendered text.
   Usage: node page_runner.js <dashboard.html> [data.json] [scenario.json]. Exits 1 on any script error.
   A scenario runs the live update with fake timers: {"hidden": true} keeps the tab hidden, {"next": {...}} is what the next
   data.js sets, {"fail": true} makes it fail to load, {"ticks": n} is how many polls run (default 1). */
"use strict";
const fs = require("fs");
const vm = require("vm");

class Node_ {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.style = { setProperty(k, v) { this[k] = v; } }; this.className = ""; this.hidden = false; this.handlers = {}; this._text = ""; this.scrollTop = 0; this.scrollLeft = 0; }
  get firstChild() { return this.children[0] || null; }
  get classList() {
    const self = this;
    const names = () => self.className.split(/\s+/).filter(Boolean);
    return {
      add(c) { if (!names().includes(c)) self.className = names().concat(c).join(" "); },
      remove(c) { self.className = names().filter((n) => n !== c).join(" "); },
      contains(c) { return names().includes(c); },
      toggle(c, on) { (on === undefined ? !names().includes(c) : on) ? this.add(c) : this.remove(c); },
    };
  }
  set textContent(v) { this.children = []; this._text = String(v); }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(" "); }
  appendChild(c) { return this.insertBefore(c, null); }
  insertBefore(c, before) {
    if (c.parentNode) c.parentNode.removeChild(c);
    const index = before ? this.children.indexOf(before) : this.children.length;
    if (index < 0) throw new Error("missing insertBefore child");
    this.children.splice(index, 0, c); c.parentNode = this; return c;
  }
  removeChild(c) { this.children.splice(this.children.indexOf(c), 1); c.parentNode = null; }
  closest(selector) {
    const matches = selector.startsWith("#") ? this === byId[selector.slice(1)] :
      selector.startsWith(".") ? this.classList.contains(selector.slice(1)) :
      selector === "[data-tip]" && this.getAttribute("data-tip") !== null;
    return matches ? this : this.parentNode ? this.parentNode.closest(selector) : null;
  }
  focus() {
    const old = document.activeElement;
    if (old && old !== this && handlers.focusout) handlers.focusout({target: old, relatedTarget: this});
    document.activeElement = this;
    if (handlers.focusin) handlers.focusin({target: this});
  }
  append(...cs) { cs.forEach((c) => this.appendChild(c)); }
  replaceChildren(...cs) {
    if (this.children.some((c) => all(c).includes(document.activeElement))) document.activeElement = document.body;
    this.children = cs;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "class") this.className = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  remove() { this.removed = true; }
  addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 300, right: 400, bottom: 300 }; }
  querySelector() { return new Node_("div"); }
  querySelectorAll() { return []; }
}

const [pagePath, dataPath, scenarioPath] = process.argv.slice(2);
const scenario = scenarioPath ? JSON.parse(fs.readFileSync(scenarioPath, "utf8")) : {};
const html = fs.readFileSync(pagePath, "utf8");
const path = require("path");
const scripts = [fs.readFileSync(path.join(path.dirname(pagePath), "dashboard.js"), "utf8")];

const byId = {};
const loads = [], timers = [], handlers = {}, windowHandlers = {};
const stored = Object.assign({}, scenario.stored);
let clock = scenario.now ? Date.parse(scenario.now) : Date.now();
class FakeDate extends Date {
  constructor(...args) { super(...(args.length ? args : [clock])); }
  static now() { return clock; }
}
const document = {
  documentElement: new Node_("html"),
  body: new Node_("body"),
  head: { appendChild(s) {
    loads.push(s.src);
    if (scenario.fail) return s.onerror();
    if (scenario.next) sandbox.window.FNL_DATA = JSON.parse(JSON.stringify(scenario.next));
    s.onload();
  } },
  visibilityState: scenario.hidden ? "hidden" : "visible",
  createElement: (t) => new Node_(t),
  createElementNS: (ns, t) => new Node_(t),
  createTextNode: (s) => { const n = new Node_("#text"); n._text = String(s); return n; },
  getElementById: (id) => byId[id] || (byId[id] = new Node_("div")),
  querySelector: (selector) => all(document.body).find((n) => selector.startsWith(".") && n.classList.contains(selector.slice(1))) || new Node_("div"),
  addEventListener(type, fn) { handlers[type] = fn; },
};
const tipValues = new WeakMap();
class ObservedWeakMap extends WeakMap {
  set(key, value) { tipValues.set(key, value); return super.set(key, value); }
}
const sandbox = {
  WeakMap: ObservedWeakMap,
  document,
  Date: FakeDate,
  console,
  setInterval: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
  window: { matchMedia: () => ({ matches: false }), addEventListener(type, fn) { windowHandlers[type] = fn; }, innerWidth: 400, innerHeight: 800,
    location: { hash: scenario.hash || "" } },
  localStorage: { getItem(k) { if (scenario.storageThrows) throw new Error("blocked"); return stored[k] || null; },
    setItem(k, v) { if (scenario.storageThrows) throw new Error("blocked"); stored[k] = String(v); } },
};
// Parse the real static shell so title-bar placement is tested, not invented by the runner.
const shell = html.split("<body>")[1].split("</body>")[0];
const parents = [document.body];
for (const token of shell.match(/<[^>]+>|[^<]+/g)) {
  if (token.startsWith("</")) { parents.pop(); continue; }
  if (token.startsWith("<")) {
    const tag = token.match(/^<([a-z0-9]+)/i)[1];
    const node = new Node_(tag);
    for (const attr of token.matchAll(/([a-z-]+)="([^"]*)"/g)) node.setAttribute(attr[1], attr[2]);
    const id = node.getAttribute("id"); if (id) byId[id] = node;
    node.hidden = /\shidden(?:\s|>)/.test(token);
    parents[parents.length - 1].appendChild(node);
    parents.push(node);
  } else if (token.trim()) parents[parents.length - 1].appendChild(document.createTextNode(token.trim()));
}

document.activeElement = document.body;
sandbox.window.document = document;
if (dataPath) sandbox.window.FNL_DATA = JSON.parse(fs.readFileSync(dataPath, "utf8"));
if (scenario.budgetValue !== undefined) {
  sandbox.window.FNL_DATA.running.open.forEach((run) => { run.budget_min = Number(scenario.budgetValue); });
}
vm.createContext(sandbox);
vm.runInContext(scripts[0], sandbox, { filename: "dashboard.html" });

const app = byId["app"];
const first = app ? app.children[0] : null;
function all(n) { return [n, ...n.children.flatMap(all)]; }
function role(value) { return all(document.body).filter((n) => n.getAttribute("role") === value); }
function namedTab(name) { return role("tab").find((n) => n.textContent.startsWith(name)); }
function namedPanel(name) { return role("tabpanel").find((n) => n.getAttribute("id") === "panel-" + name); }
function fire(n, type, key) {
  if (!n) throw new Error("missing event target");
  const event = { target: n, key, clientX: 10, clientY: 10, preventDefault() {} };
  (n.handlers[type] || []).forEach((fn) => fn(event));
  if (handlers[type]) handlers[type](event);
}
const states = [], tipStates = [];
function tooltipState() {
  const tip = byId.tip;
  return {hidden: tip.hidden, text: tip.textContent, attrs: {...tip.attrs}, picture: picture(tip)};
}
function tooltipAction(action) {
  if (!action.tooltip) return;
  const legacyPane = action.scope === "project" ? "projects, last 24 h" : "running now";
  const scope = action.scope === "prompt" ? all(app).find((n) => n.className === "cmd") : action.scope === "footer" ? all(app).find((n) => n.className === "status") : ["agents", "project"].includes(action.scope || "agents") ?
    all(namedPanel("now")).find((n) => n.tag === "section" && n.children[0].textContent.startsWith(legacyPane)) : namedPanel(action.scope);
  const target = all(scope).find((n) => action.target === "merged" ?
    n.classList.contains("task-brick") && Number(n.getAttribute("data-count")) > 1 :
    action.scope === "prompt" ? n === scope : n.classList.contains(action.target || "info-button"));
  switch (action.tooltip) {
    case "focus": target.focus(); break;
    case "hover": fire(target, "pointermove"); break;
    case "leave": fire(document.body, "pointermove"); break;
    case "blur": document.body.focus(); break;
    case "tap": fire(target, "pointerdown"); fire(target, "click"); break;
    case "escape": fire(document.activeElement, "keydown", "Escape"); break;
    case "outside": fire(document.body, "pointerdown"); break;
    case "surface": fire(byId.tip, "pointermove"); fire(byId.tip, "pointerdown"); break;
    default: throw new Error("unknown tooltip action");
  }
  tipStates.push(tooltipState());
}
function state() { return { selected: role("tab").filter((n) => n.getAttribute("aria-selected") === "true").map((n) => n.textContent.split(" ")[0]),
  focused: document.activeElement ? document.activeElement.textContent.split(" ")[0] : null }; }
for (const action of scenario.actions || []) {
  if (action.click) fire(namedTab(action.click), "click");
  if (action.key) fire(namedTab(action.tab), "keydown", action.key);
  if (action.hash !== undefined) { sandbox.window.location.hash = action.hash; windowHandlers.hashchange(); }
  if (action.panel) {
    const panel = namedPanel(action.panel);
    panel.scrollTop = action.scrollTop || 0; panel.scrollLeft = action.scrollLeft || 0;
    if (action.open !== undefined) all(panel).filter((n) => n.tag === "details").forEach((n) => n.open = action.open);
  }
  tooltipAction(action);
  states.push(state());
}
if (scenarioPath) for (let i = 0; i < (scenario.ticks || 1); i++) {
  clock += scenario.advance_ms || 0;
  timers.forEach((x) => x.fn());
}
for (const action of scenario.after || []) {
  if (action.click) fire(namedTab(action.click), "click");
  tooltipAction(action);
  states.push(state());
}
if (scenario.reveal) { document.visibilityState = "visible"; handlers.visibilitychange(); }
const out = { text: app ? app.textContent.replace(/\s+/g, " ").trim() : "", cells: 0, svg: 0, openRings: 0, tags: [], loads, poll_ms: timers.map((x) => x.ms), redrawn: !!first && app.children[0] !== first };
(function walk(n) { out.tags.push(n.tag); out.openRings += n.className === "dot open" ? 1 : 0; out.cells += n.className.split(" ").includes("dy") ? 1 : 0; out.svg += n.tag === "svg" ? 1 : 0; n.children.forEach(walk); })(app || new Node_("x"));
function picture(n, disclosure, hidden, panel) {
  if (n.getAttribute("role") === "tabpanel") panel = n.getAttribute("id");
  disclosure = disclosure || (n.tag === "details" ? n.children[0].textContent : null);
  hidden = hidden || n.hidden;
  const spec = tipValues.get(n);
  const tooltip = typeof spec === "string" ? spec : spec ? [spec.title, spec.sub,
    ...(spec.rows || []).map((row) => row.join(": ")), ...(spec.items || []), ...(spec.chips || []).map((chip) => chip.label)].filter(Boolean).join(" ") : null;
  return [{ tooltip, spec, tag: n.tag, cls: n.className, text: n.textContent, attrs: n.attrs, style: n.style,
    disclosure, panel, open: !!n.open, hidden: !!hidden }, ...n.children.flatMap((child) => picture(child, disclosure, hidden, panel))];
}
out.picture = picture(app);
out.chrome = picture(document.querySelector(".bar"));
out.dom = picture(document.body).map((n) => ({tag: n.tag, attrs: n.attrs}));
out.states = states;
out.tip = tooltipState(); out.tipStates = tipStates;
out.panelChildren = role("tabpanel").map((n) => n.children.map((c) => ({tag: c.tag, cls: c.className, text: c.textContent})));
out.focused = document.activeElement ? document.activeElement.textContent.split(" ")[0] : null;
out.stored = stored;
out.hash = sandbox.window.location.hash;
out.tabs = role("tab").map((n) => ({ text: n.textContent, attrs: n.attrs, tabIndex: n.tabIndex, inTitleBar: !!n.closest(".bar") }));
out.panels = role("tabpanel").map((n) => ({ attrs: n.attrs, hidden: n.hidden, text: n.textContent,
  scrollTop: n.scrollTop, scrollLeft: n.scrollLeft, open: all(n).filter((x) => x.tag === "details").map((x) => !!x.open) }));
out.shared = app.children.filter((n) => !["tablist", "tabpanel"].includes(n.getAttribute("role"))).map((n) => n.className);
process.stdout.write(JSON.stringify(out));
