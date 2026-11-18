/* Runs one ui-review-gate snippet against a small fake DOM and prints the JSON string it returns.
   Usage: node ui_snippet_runner.js <snippet.js> <tree.json> <viewport width>. Exits 1 on any script error.
   tree.json is the fixture page parsed by the Python test: {"tag", "attrs", "children"} nodes, text as {"text"}.
   There is no layout engine and no browser: an element's box is the left, top, width and height of its style
   attribute; computed style is that attribute plus inheritance of colour, font and visibility. The real cascade,
   layout and rendering are not exercised here. */
"use strict";
const fs = require("fs");
const vm = require("vm");

const [snippetPath, treePath, viewportArg] = process.argv.slice(2);
const viewport = Number(viewportArg);
const INHERITED = ["color", "fontSize", "fontWeight", "visibility"];
const DEFAULTS = { color: "rgb(0, 0, 0)", fontSize: "16px", fontWeight: "400", visibility: "visible",
  backgroundColor: "rgba(0, 0, 0, 0)", backgroundImage: "none", opacity: "1", overflow: "visible",
  overflowX: "visible", borderTopWidth: "0px", borderTopColor: "rgb(0, 0, 0)", position: "static" };
const INLINE = new Set(["a", "span", "label", "strong", "em", "b", "i"]);
const camel = (k) => k.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());

class Text_ {
  constructor(text, parent) { this.nodeType = 3; this.textContent = text; this.parentElement = parent; }
}
class Element_ {
  constructor(node, parent) {
    this.nodeType = 1;
    this.tagName = node.tag.toUpperCase();
    this.attrs = node.attrs || {};
    this.parentElement = parent;
    this.declared = {};
    for (const part of (this.attrs.style || "").split(";")) {
      const at = part.indexOf(":");
      if (at > 0) this.declared[camel(part.slice(0, at))] = part.slice(at + 1).trim();
    }
    this.childNodes = (node.children || []).map((c) => (c.text !== undefined ? new Text_(c.text, this) : new Element_(c, this)));
    this.children = this.childNodes.filter((c) => c.nodeType === 1);
  }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  box() {
    const n = (k) => parseFloat(this.declared[k]) || 0;
    return { left: n("left"), top: n("top"), width: n("width"), height: n("height") };
  }
  getBoundingClientRect() {
    const b = this.box();
    return { ...b, x: b.left, y: b.top, right: b.left + b.width, bottom: b.top + b.height };
  }
  descendants() { return this.children.flatMap((c) => [c, ...c.descendants()]); }
  get clientWidth() { return this.tagName === "HTML" ? viewport : this.box().width; }
  get scrollWidth() {
    if (this.tagName === "HTML") {
      const outside = this.descendants().filter((e) => !e.inRegion());
      return Math.max(viewport, ...outside.map((e) => e.box().left + e.box().width));
    }
    const own = this.box();
    return Math.max(own.width, ...this.descendants().map((e) => e.box().left + e.box().width - own.left));
  }
  inRegion() {
    for (let p = this.parentElement; p; p = p.parentElement) {
      if (/^(auto|scroll)$/.test(p.declared.overflowX || p.declared.overflow || "")) return true;
    }
    return false;
  }
}

const style = (el) => {
  const out = {};
  for (const [k, v] of Object.entries(DEFAULTS)) {
    if (k in el.declared) out[k] = el.declared[k];
    else if (INHERITED.includes(k) && el.parentElement) out[k] = style(el.parentElement)[k];
    else out[k] = v;
  }
  out.display = el.declared.display || (INLINE.has(el.tagName.toLowerCase()) ? "inline" : "block");
  return out;
};

const tree = JSON.parse(fs.readFileSync(treePath, "utf8"));
const root = new Element_(tree, null);
const all = [root, ...root.descendants()];
const body = all.find((e) => e.tagName === "BODY");
const document = {
  documentElement: root,
  body,
  querySelectorAll(selector) {
    if (selector === "*") return all;
    if (selector === "body *") return body.descendants();
    throw new Error("the fake DOM supports only '*' and 'body *', got " + selector);
  },
};
const sandbox = { document, getComputedStyle: style, window: { innerWidth: viewport }, JSON, Math, Array, Set, Object,
  parseFloat, parseInt };
sandbox.window.getComputedStyle = style;
try {
  const result = vm.runInNewContext(fs.readFileSync(snippetPath, "utf8"), sandbox, { timeout: 5000 });
  if (typeof result !== "string") throw new Error("the snippet must return a JSON string");
  process.stdout.write(result);
} catch (error) {
  process.stderr.write(String(error && error.stack || error) + "\n");
  process.exit(1);
}
