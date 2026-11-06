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
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children.splice(this.children.indexOf(c), 1); }
  focus() { document.activeElement = this; }
  append(...cs) { cs.forEach((c) => this.appendChild(c)); }
  replaceChildren(...cs) {
    if (this.children.some((c) => all(c).includes(document.activeElement))) document.activeElement = document.body;
    this.children = cs;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
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
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
if (scripts.length !== 1) throw new Error("expected one inline script, found " + scripts.length);

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
  querySelector: () => new Node_("div"),
  addEventListener(type, fn) { handlers[type] = fn; },
};
const sandbox = {
  document,
  Date: FakeDate,
  console,
  setInterval: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
  window: { matchMedia: () => ({ matches: false }), addEventListener(type, fn) { windowHandlers[type] = fn; }, innerWidth: 400,
    location: { hash: scenario.hash || "" } },
  localStorage: { getItem(k) { if (scenario.storageThrows) throw new Error("blocked"); return stored[k] || null; },
    setItem(k, v) { if (scenario.storageThrows) throw new Error("blocked"); stored[k] = String(v); } },
};
document.activeElement = document.body;
sandbox.window.document = document;
if (dataPath) sandbox.window.FNL_DATA = JSON.parse(fs.readFileSync(dataPath, "utf8"));
vm.createContext(sandbox);
vm.runInContext(scripts[0], sandbox, { filename: "dashboard.html" });

const app = byId["app"];
const first = app ? app.children[0] : null;
function all(n) { return [n, ...n.children.flatMap(all)]; }
function role(value) { return all(app).filter((n) => n.getAttribute("role") === value); }
function namedTab(name) { return role("tab").find((n) => n.textContent.startsWith(name)); }
function namedPanel(name) { return role("tabpanel").find((n) => n.getAttribute("id") === "panel-" + name); }
function fire(n, type, key) {
  if (!n) throw new Error("missing event target");
  (n.handlers[type] || []).forEach((fn) => fn({ target: n, key, preventDefault() {} }));
}
const states = [];
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
  states.push(state());
}
if (scenarioPath) for (let i = 0; i < (scenario.ticks || 1); i++) {
  clock += scenario.advance_ms || 0;
  timers.forEach((x) => x.fn());
}
for (const action of scenario.after || []) {
  if (action.click) fire(namedTab(action.click), "click");
  states.push(state());
}
if (scenario.reveal) { document.visibilityState = "visible"; handlers.visibilitychange(); }
const out = { text: app ? app.textContent.replace(/\s+/g, " ").trim() : "", cells: 0, svg: 0, openRings: 0, tags: [], loads, poll_ms: timers.map((x) => x.ms), redrawn: !!first && app.children[0] !== first };
(function walk(n) { out.tags.push(n.tag); out.openRings += n.className === "dot open" ? 1 : 0; out.cells += n.className.split(" ").includes("dy") ? 1 : 0; out.svg += n.tag === "svg" ? 1 : 0; n.children.forEach(walk); })(app || new Node_("x"));
function picture(n, disclosure, hidden) {
  disclosure = disclosure || (n.tag === "details" ? n.children[0].textContent : null);
  hidden = hidden || n.hidden;
  return [{ tag: n.tag, cls: n.className, text: n.textContent, attrs: n.attrs, style: n.style,
    disclosure, hidden: !!hidden }, ...n.children.flatMap((child) => picture(child, disclosure, hidden))];
}
out.picture = picture(app);
out.states = states;
out.focused = document.activeElement ? document.activeElement.textContent.split(" ")[0] : null;
out.stored = stored;
out.hash = sandbox.window.location.hash;
out.tabs = role("tab").map((n) => ({ text: n.textContent, attrs: n.attrs, tabIndex: n.tabIndex }));
out.panels = role("tabpanel").map((n) => ({ attrs: n.attrs, hidden: n.hidden, text: n.textContent,
  scrollTop: n.scrollTop, scrollLeft: n.scrollLeft, open: all(n).filter((x) => x.tag === "details").map((x) => !!x.open) }));
out.shared = app.children.filter((n) => !["tablist", "tabpanel"].includes(n.getAttribute("role"))).map((n) => n.className);
process.stdout.write(JSON.stringify(out));
