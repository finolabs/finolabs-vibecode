/* Runs the script of skills/fnl-status/assets/dashboard.html against a small fake DOM and prints the rendered text.
   Usage: node page_runner.js <dashboard.html> [data.json]. Exits 1 on any script error. */
"use strict";
const fs = require("fs");
const vm = require("vm");

class Node_ {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.style = { setProperty(k, v) { this[k] = v; } }; this.className = ""; this.hidden = false; this.handlers = {}; this._text = ""; }
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
  append(...cs) { cs.forEach((c) => this.appendChild(c)); }
  replaceChildren(...cs) { this.children = cs; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 300, right: 400, bottom: 300 }; }
  querySelector() { return new Node_("div"); }
  querySelectorAll() { return []; }
}

const [pagePath, dataPath] = process.argv.slice(2);
const html = fs.readFileSync(pagePath, "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
if (scripts.length !== 1) throw new Error("expected one inline script, found " + scripts.length);

const byId = {};
const document = {
  documentElement: new Node_("html"),
  body: new Node_("body"),
  createElement: (t) => new Node_(t),
  createElementNS: (ns, t) => new Node_(t),
  createTextNode: (s) => { const n = new Node_("#text"); n._text = String(s); return n; },
  getElementById: (id) => byId[id] || (byId[id] = new Node_("div")),
  querySelector: () => new Node_("div"),
  addEventListener() {},
};
const sandbox = {
  document,
  console,
  window: { matchMedia: () => ({ matches: false }), addEventListener() {}, innerWidth: 400 },
  localStorage: { getItem: () => null, setItem() {} },
};
sandbox.window.document = document;
if (dataPath) sandbox.window.FNL_DATA = JSON.parse(fs.readFileSync(dataPath, "utf8"));
vm.createContext(sandbox);
vm.runInContext(scripts[0], sandbox, { filename: "dashboard.html" });

const app = byId["app"];
const out = { text: app ? app.textContent.replace(/\s+/g, " ").trim() : "", cells: 0, svg: 0 };
(function walk(n) { out.cells += n.className.split(" ").includes("dy") ? 1 : 0; out.svg += n.tag === "svg" ? 1 : 0; n.children.forEach(walk); })(app || new Node_("x"));
process.stdout.write(JSON.stringify(out));
