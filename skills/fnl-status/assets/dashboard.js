(function () {
  "use strict";
  /* data.js sits beside this page and sets window.FNL_DATA; without it the page shows an empty state. */
  function dataNow() { return window.FNL_DATA && typeof window.FNL_DATA === "object" ? window.FNL_DATA : null; }
  var D = dataNow();
  var app = document.getElementById("app"), tip = document.getElementById("tip");

  /* Theme switch: follows the viewer until clicked, then remembers the choice when storage allows. */
  var root = document.documentElement, KEY = "fnl-theme";
  function current() {
    var a = root.getAttribute("data-theme");
    if (a === "dark" || a === "light") return a;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  function paint() {
    var c = current();
    document.getElementById("th-dark").setAttribute("aria-pressed", String(c === "dark"));
    document.getElementById("th-light").setAttribute("aria-pressed", String(c === "light"));
  }
  function setTheme(v) {
    root.setAttribute("data-theme", v);
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage can be blocked */ }
    paint();
  }
  try { var saved = localStorage.getItem(KEY); if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved); } catch (e) { /* storage can be blocked */ }
  document.getElementById("th-dark").addEventListener("click", function () { setTheme("dark"); });
  document.getElementById("th-light").addEventListener("click", function () { setTheme("light"); });
  paint();

  /* Builders: every value reaches the page as text or an attribute, never as markup. */
  var NS = "http://www.w3.org/2000/svg";
  function h(tag, cls, kids) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    (kids || []).forEach(function (k) { if (k != null) el.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return el;
  }
  function t(tag, cls, text) { return h(tag, cls, [String(text)]); }
  function s(tag, attrs) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, String(attrs[k])); });
    return el;
  }
  var tips = new WeakMap();
  function tipSentence(spec) {
    if (typeof spec === "string") return spec;
    return [spec.title, spec.sub].concat((spec.rows || []).map(function (row) { return row[0] + ": " + row[1]; }),
      spec.items || [], (spec.reviewChains || []).map(function (vs) { return vs.length + " rounds: " + vs.join(" → "); }), (spec.chips || []).map(function (chip) { return chip.label; })).filter(Boolean).map(function (part) { return String(part).replace(/[.!?]+$/, ""); }).join("; ").replace(/\s+/g, " ") + ".";
  }
  function tipOn(el, spec) {
    tips.set(el, spec); el.setAttribute("data-tip", "");
    if (typeof spec !== "string") {
      el.setAttribute("aria-label", tipSentence(spec)); el.setAttribute("aria-describedby", "tip");
      el.setAttribute("tabindex", "0");
    }
    return el;
  }
  function renderTip(spec) {
    tip.textContent = "";
    if (typeof spec === "string") { tip.textContent = spec; return; }
    tip.appendChild(t("div", "tip-title", spec.title || ""));
    if (spec.sub) tip.appendChild(t("div", "tip-sub", spec.sub));
    tip.appendChild(h("div", "tip-divider"));
    if (spec.rows && spec.rows.length) {
      var grid = h("div", "tip-rows");
      spec.rows.forEach(function (row) { grid.appendChild(t("span", "tip-label", row[0])); grid.appendChild(t("span", "tip-value", row[1])); });
      tip.appendChild(grid);
    }
    (spec.items || []).slice(0, 5).forEach(function (item) { tip.appendChild(t("div", "tip-item", item)); });
    if (spec.chips && spec.chips.length) {
      var chips = h("div", "tip-chips");
      spec.chips.forEach(function (chip) {
        var state = ["done", "active", "accepted", "todo", "over"].indexOf(chip.state) !== -1 ? chip.state : "todo";
        chips.appendChild(h("span", "tip-chip " + state, [h("i", "tip-dot"), String(chip.label)]));
      });
      tip.appendChild(chips);
    }
    if (spec.reviewChains) {
      var chains = h("div", "tip-review-chains");
      spec.reviewChains.forEach(function (verdicts) {
        var chain = h("div", "tip-review-chain");
        chain.setAttribute("aria-label", verdicts.length + " rounds: " + verdicts.join(" → "));
        verdicts.slice(0, 8).forEach(function (verdict) {
          var dot = h("i", "review-dot " + (verdict === "APPROVE" ? "approve" : "rework"));
          dot.setAttribute("aria-label", verdict); chain.appendChild(dot);
        });
        if (verdicts.length > 8) chain.appendChild(t("span", "more-rounds", "+" + (verdicts.length - 8)));
        chains.appendChild(chain);
      });
      tip.appendChild(chains);
    }
    if (spec.bar && Number.isFinite(spec.bar.max) && spec.bar.max > 0) {
      var bar = h("div", "tip-bar"), ink = h("i", "tip-bar-fill");
      ink.style.width = Math.max(0, Math.min(100, spec.bar.value / spec.bar.max * 100)) + "%";
      bar.appendChild(ink);
      (spec.bar.marks || []).forEach(function (value) {
        var mark = h("i", "tip-bar-mark"); mark.style.left = Math.max(0, Math.min(100, value / spec.bar.max * 100)) + "%"; bar.appendChild(mark);
      });
      bar.setAttribute("aria-hidden", "true"); tip.appendChild(bar);
    }
  }
  function infoButton(text) {
    var button = t("button", "info-button", "ⓘ");
    button.setAttribute("type", "button"); button.setAttribute("tabindex", "0");
    button.setAttribute("aria-label", "About this data");
    button.setAttribute("aria-describedby", "tip"); button.setAttribute("aria-expanded", "false");
    return tipOn(button, text);
  }
  function budgetMinutes(value) {
    return Number.isFinite(value) && value > 0 && value <= 1000000 ? value : null;
  }
  function pct(v) { return v == null ? "—" : Math.round(v * 100) + "%"; }
  function num(v) { return v == null ? "—" : String(v); }
  function tok(v) { return v >= 1000 ? (Math.round(v / 100) / 10) + "k" : String(v); }
  function missing(k) { return D.missing && D.missing[k]; }
  function stack(kids) { var g = h("div", "", kids); g.style.display = "grid"; g.style.gap = "12px"; return g; }
  function swatch(c) { var b = h("b"); b.style.background = c; return b; }
  function legend(items) { return h("div", "legend", items.map(function (i) { return h("span", "", [swatch(i[1]), i[0]]); })); }
  /* Placeholder shapes keep an empty pane the size of a filled one. */
  var GW = ["92%", "78%", "60%", "44%", "36%", "28%", "22%", "16%"];
  function ghost(w, hgt) { var g = h("i", "ghost"); g.style.width = w; g.style.height = hgt || "12px"; return g; }
  function ghostBars(n) {
    var rows = [];
    for (var i = 0; i < n; i++) rows.push(h("div", "r", [ghost("64%", "10px"), h("span", "trk", [ghost(GW[i % GW.length])])]));
    return h("div", "hb", rows);
  }
  function ghostCal() {
    var cells = [];
    for (var i = 0; i < 35; i++) cells.push(h("div", "dy ghost"));
    var side = h("div", "calside", [ghost("40px", "22px"), ghost("90px", "22px"), ghost("70px", "22px"), ghost("100%", "48px")]);
    return h("div", "calwrap", [h("div", "calmain", [h("div", "calnav", [ghost("24px", "24px"), ghost("110px", "14px"), ghost("24px", "24px")]), h("div", "cal", cells)]), side]);
  }
  function ghostRows(n, tall) {
    var rows = [];
    for (var i = 0; i < n; i++) rows.push(h("div", "grow", [ghost("70%", "12px"), ghost(GW[(i * 2) % GW.length], tall ? "16px" : "12px")]));
    return stack(rows);
  }
  var GHOSTS = {
    cal: ghostCal,
    stack: function () { return stack([ghost("100%", "16px"), ghost("44%", "6px"), ghost("82%", "10px")]); },
    bars3: function () { return stack([ghostBars(3), ghost("40%", "10px")]); },
    bars4: function () { return ghostBars(4); },
    bars8: function () { return ghostBars(8); },
    rv: function () { return stack([ghost("46%", "28px"), ghostRows(3), ghost("34%", "10px")]); },
    dl: function () { return stack([ghostRows(3, true), ghost("50%", "10px")]); }
  };
  function pane(title, aside, cls, content, why, ghostKind) {
    var p = h("section", "pane" + (cls ? " " + cls : "")), b = h("div", "body");
    p.appendChild(h("h2", "", [t("span", "", title), typeof aside === "string" ? t("span", "", aside) : h("span", "pane-aside", [aside])]));
    if (content) b.appendChild(content);
    else {
      b.appendChild(t("div", "nodata", "no data: " + (why || "source missing")));
      if (GHOSTS[ghostKind]) b.appendChild(GHOSTS[ghostKind]());
    }
    p.appendChild(b);
    return p;
  }
  function runningLimits() {
    var snapshot = D.running && D.running.snapshot || {};
    return {title: "How to read this", items: [
      "Lanes show elapsed time against budget and cap.",
      "Ticks mark half budget and budget; red means over budget.",
      "Slots count open dispatches, not identified sessions.",
      "Quota bricks show cached remaining capacity; ? is unverified.",
      "Processes are machine-wide, current user only; liveness is advisory" +
        (snapshot.reason || !snapshot.time ? "; " + (snapshot.reason || "snapshot unavailable") : ".")
    ]};
  }
  var brickId = 0;
  function brick(state, width, height, cls) {
    var svg = s("svg", {width: width, height: height + 3, viewBox: "0 0 " + width + " " + (height + 3),
      "class": "lego-brick " + state + (cls ? " " + cls : ""), "aria-hidden": "true"});
    var ink = {done: "var(--h2)", active: "var(--p)", accepted: "var(--warn)", low: "var(--crit)", todo: "none"}[state] || "none";
    var group = s("g", {"class": "brick-ink"});
    [0.22, 0.58].forEach(function (x) {
      group.appendChild(s("rect", {x: width * x, y: 0, width: width * .2, height: 3, rx: 1,
        fill: state === "todo" ? "var(--line)" : ink, "class": "brick-stud"}));
    });
    var body = s("rect", {x: .5, y: 3.5, width: width - 1, height: height - 1, rx: 2,
      fill: ink, stroke: state === "todo" ? "var(--line)" : "none", "stroke-width": 1, "class": "brick-body"});
    if (state === "accepted" || state === "active" && cls && cls.indexOf("package-brick") !== -1) {
      var id = "brick-hatch-" + (++brickId), defs = s("defs"), pattern = s("pattern", {
        id: id, width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)"});
      pattern.appendChild(s("rect", {width: 2, height: 4, fill: state === "active" ? "var(--p)" : "var(--warn)"}));
      defs.appendChild(pattern); svg.appendChild(defs); body.setAttribute("fill", "url(#" + id + ")");
    }
    group.appendChild(body); svg.appendChild(group);
    return svg;
  }
  function quotaPoolMark(name) {
    var weekly = /week/i.test(name), clock = /five.hour|session|5h/i.test(name);
    if (!weekly && !clock) return t("span", "quota-pool-name", name.slice(0, 8));
    var icon = s("svg", {width: 14, height: 14, viewBox: "0 0 16 16", "class": "quota-pool-icon", "aria-hidden": "true"});
    var ink = {fill: "none", stroke: "currentColor", "stroke-width": 1.2, "stroke-linecap": "round"};
    if (weekly) {
      icon.appendChild(s("rect", Object.assign({x: 2, y: 3, width: 12, height: 11, rx: 1.5}, ink)));
      icon.appendChild(s("path", Object.assign({d: "M5 1V5M11 1V5M2 7H14M5 10H11"}, ink)));
    } else {
      icon.appendChild(s("circle", Object.assign({cx: 8, cy: 8, r: 6}, ink)));
      icon.appendChild(s("path", Object.assign({d: "M8 4V8L11 10"}, ink)));
    }
    return icon;
  }
  function runningPanel() {
    if (!D.running) return null;
    var r = D.running, snapshot = r.snapshot || {}, processes = r.processes || [], open = r.open || [];
    var available = !!snapshot.time && !snapshot.reason;
    var late = open.filter(function (run) { return budgetMinutes(run.budget_min) != null && run.age_min >= run.budget_min / 2; }).length;
    var unowned = processes.filter(function (p) { return p.not_started_by_coordinator; }).length;
    var lanes = h("div", "lanes");
    open.slice().sort(function (a, b) {
      var ab = budgetMinutes(a.budget_min), bb = budgetMinutes(b.budget_min);
      var ar = ab ? Math.max(ab * 4 / 3, ab + 10) - a.age_min : Infinity;
      var br = bb ? Math.max(bb * 4 / 3, bb + 10) - b.age_min : Infinity;
      return ar - br;
    }).forEach(function (run) {
      var budget = budgetMinutes(run.budget_min), age = Number(run.age_min) || 0;
      var cap = budget > 0 ? Math.max(budget * 4 / 3, budget + 10) : null;
      var state = cap && age > cap ? "cap" : budget > 0 ? age > budget ? "over" : age >= budget / 2 ? "check" : "within" : "unknown";
      var W = 560, H = 8, track = s("svg", {"class": "lane-track", width: "100%", height: 14,
        role: "img", "aria-label": age + "/" + (cap || "?") + " minutes of track"});
      var clipId = "lane-clip-" + (++brickId), defs = s("defs"), clip = s("clipPath", {id: clipId});
      clip.appendChild(s("rect", {x: 0, y: 3, width: "100%", height: H, rx: 4}));
      defs.appendChild(clip); track.appendChild(defs);
      track.appendChild(s("rect", {"class": "lane-ground", x: 0, y: 3, width: "100%", height: H, rx: 4, fill: "var(--lane-track)"}));
      // The outer SVG has CSS-pixel units so corners stay 4 px and ticks stay 1 px at every width.
      // Only the inner amount scale stretches; both segments share its snapped edge.
      var clipped = s("g", {"clip-path": "url(#" + clipId + ")"});
      var scale = s("svg", {x: 0, y: 3, width: "100%", height: H, viewBox: "0 0 560 8", preserveAspectRatio: "none"});
      var fill = s("g", {"class": "lane-fill"});
      var used = cap ? Math.round(Math.max(0, Math.min(W, age / cap * W)) * 2) / 2 : 0;
      var half = cap ? budget / 2 / cap * W : 0, end = cap ? Math.round(budget / cap * W * 2) / 2 : 0;
      var edge = Math.min(used, end);
      [["brand", 0, edge, "var(--p)"], ["red", edge, used - edge, "var(--crit)"]].forEach(function (part) {
        fill.appendChild(s("rect", {"class": "lane-segment " + part[0], x: part[1], y: 0, width: part[2], height: H,
          "shape-rendering": "crispEdges", fill: part[3]}));
      });
      scale.appendChild(fill); clipped.appendChild(scale); track.appendChild(clipped);
      if (cap) [["check", half, "check deadline: half budget"], ["budget", end, "budget"]].forEach(function (item) {
        track.appendChild(tipOn(s("rect", {"class": "lane-tick " + item[0] + "-tick", x: item[1] / W * 100 + "%", transform: "translate(-.5 0)", y: 0, width: 1,
          height: 14, fill: "var(--faint)"}), item[2]));
      });
      var label = h("div", "lane-label", [t("span", "lane-identity", (run.agent || "other") + " " + (run.model || "—")),
        t("span", "lane-task", run.task || "—")]);
      if (run.no_process_found) {
        var marker = tipOn(brick("todo", 12, 6, "no-process"), {title: "no process", items: ["No process found."]});
        marker.setAttribute("aria-hidden", "false"); marker.setAttribute("role", "img");
        marker.setAttribute("aria-label", "no process found"); marker.setAttribute("tabindex", "0");
        label.appendChild(marker);
      }
      var lane = h("div", "lane" + (run.no_process_found ? "" : " live"), [label, track,
        t("span", "lane-value", age + "/" + (budget == null ? "?" : budget) + " m")]);
      lane.setAttribute("data-run", run.id || ""); lane.setAttribute("data-state", state);
      tipOn(lane, {title: (run.agent || "other") + " " + (run.model || "—"), sub: run.task || "—",
        rows: [["elapsed", age + " min"], ["budget", budget == null ? "unknown" : budget + " min"],
          ["check at", budget == null ? "unknown" : budget / 2 + " min"], ["cap", cap == null ? "unknown" : cap + " min"]],
        bar: {value: age, max: cap, marks: budget == null ? [] : [budget / 2, budget]}});
      lanes.appendChild(lane);
    });
    if (!open.length) {
      var ghosts = h("div", "ghost-bricks");
      for (var i = 0; i < 3; i++) ghosts.appendChild(brick("todo", 48, 16, "ghost-brick"));
      lanes.appendChild(ghosts); lanes.appendChild(t("div", "nodata", "No open dispatches"));
    }
    var quota = r.quota || [], capacity = h("div", "agent-capacity");
    var limit = Number(r.parallel_limit);
    limit = Number.isInteger(limit) && limit > 0 ? Math.min(100, limit) : 5;
    var slots = h("div", "slots");
    slots.setAttribute("role", "img"); slots.setAttribute("tabindex", "0");
    for (var slot = 0; slot < limit; slot++) slots.appendChild(brick(slot < open.length ? "done" : "todo", 18, 10, "slot" + (slot < open.length ? " lit" : "")));
    tipOn(slots, {title: "slots", rows: [["lit", Math.min(open.length, limit) + " of " + limit]]});
    slots.setAttribute("aria-label", Math.min(open.length, limit) + " of " + limit + " slots lit");
    capacity.appendChild(h("div", "capacity-block", [t("div", "capacity-caption", "slots (" + limit + ")"), slots]));
    var live = r.live || {}, liveMarks = h("div", "live-sessions");
    ["claude", "codex", "antigravity"].forEach(function (family) {
      var value = live[family], count = Number.isInteger(value) && value >= 0 ? Math.min(99, value) : "?";
      var mark = t("span", "live-session", {claude: "●", codex: "◆", antigravity: "▲"}[family] + " " + count);
      mark.setAttribute("tabindex", "0");
      tipOn(mark, {title: family + " live sessions", rows: [["sessions", count]], items: [
        "sessions with activity in the last 15 min, from usage events; not a process count; a session idle longer is not shown",
        available ? "Both usage-session counts and the process snapshot exist; process counts are in the data tables." : "Process snapshot unavailable: " + (snapshot.reason || "not read")
      ]});
      liveMarks.appendChild(mark);
    });
    capacity.appendChild(h("div", "capacity-block live-block", [t("div", "capacity-caption", "active · 15 min"), liveMarks]));
    var quotaRows = [];
    quota.forEach(function (family) {
      var pools = (family.pools || []).slice(0, 8), group = h("div", "quota-pools");
      (pools.length ? pools : [null]).forEach(function (q) {
        var fraction = q ? Math.max(0, Math.min(1, Number(q.remaining_fraction) || 0)) : 0;
        var measured = q ? Date.parse(q.measured) : NaN;
        var stale = !q || q.unverified || !Number.isFinite(measured) || Date.now() < measured || (Date.now() - measured) / 1000 > 28800;
        var meter = h("div", "quota-bricks" + (stale ? " unverified" : "") + (!q ? " unread" : ""));
        var lit = fraction > 0 ? Math.max(1, Math.round(fraction * 10)) : 0;
        for (var i = 0; i < 10; i++) meter.appendChild(brick(stale || i >= lit ? "todo" : fraction <= .1 ? "low" : "done", 14, 7,
          "quota-brick" + (!stale && i < lit ? " lit" : "")));
        if (stale) meter.appendChild(t("span", "quota-unknown", "?"));
        meter.setAttribute("role", "img"); meter.setAttribute("tabindex", "0");
        tipOn(meter, q ? {title: family.agent + " quota", sub: q.name + (stale ? " · unverified" : ""),
          rows: [["remaining", Math.round(fraction * 100) + "%"], ["resets", q.resets || "unknown"], ["measured", q.measured]],
          bar: {value: fraction, max: 1, marks: [.1]}} : {title: family.agent + " quota", sub: "not read",
          items: ["quota probe off or no reading yet; turn on in fnl-setup"]});
        var label = q ? quotaPoolMark(q.name || "pool") : t("span", "quota-pool-name", "—");
        group.appendChild(h("div", "quota-pool", [label, meter]));
        if (q) quotaRows.push([family.agent, q.name, pct(fraction), q.resets || "unknown", q.measured, stale ? "unverified" : "verified"]);
      });
      capacity.appendChild(h("div", "quota-block capacity-block", [t("div", "capacity-caption", family.agent + " quota"), group]));
    });
    if (quotaRows.length) TABS.get("now").tableRows.push(tableOf("quota", ["family", "pool", "remaining", "resets", "measured", "state"], quotaRows));
    TABS.get("now").tableRows.push(tableOf("live sessions", ["family", "active in last 15 min"],
      ["claude", "codex", "antigravity"].map(function (family) { return [family, live[family] == null ? "unknown" : live[family]]; })));
    TABS.get("now").tableRows.push(tableOf("agent state", ["measure", "count"], [
      ["running now", open.length], ["parallel slots", limit], ["past the check time", late], ["not started by coordinator", unowned],
      ["named processes", available ? processes.length : "unavailable"],
      ["app processes", available ? Object.keys(snapshot.apps || {}).reduce(function (sum, family) { return sum + snapshot.apps[family]; }, 0) : "unavailable"]]));
    if (available) TABS.get("now").tableRows.push(tableOf("process roots", ["family", "elapsed seconds", "descendants", "coordinator match"], processes.map(function (p) {
      return [p.family, p.elapsed_seconds, Object.keys(p.descendants || {}).map(function (name) { return name + ": " + p.descendants[name]; }).join(", ") || "none",
        p.not_started_by_coordinator ? "not started by coordinator" : "family match only"];
    })));
    TABS.get("now").tableRows.push(tableOf("dispatch budgets", ["agent / model / task", "elapsed / budget", "check", "liveness"], open.map(function (run) {
      return [run.agent + " / " + run.model + " / " + run.task, run.age_min + "/" + run.budget_min + " min", run.check_due ? "check due" : "—", run.liveness];
    })));
    return stack([lanes, capacity]);
  }
  function projectData(p) {
    var lines = [];
    function line(value) { lines.push(t("div", "running-row", value)); }
    var allTasks = [], total = 0, done = 0;
    (p.features || []).forEach(function (f) { total += f.total; done += f.done; allTasks = allTasks.concat(f.tasks || []); });
    var active = allTasks.filter(function (task) { return task.state === "in progress"; }).length;
    if (p.source && p.source !== "none") {
      var itemStates = ["done", "active", "todo", "unknown", "deferred", "needs-attention"];
      lines.push(tableOf("pipeline items", itemStates, [itemStates.map(function (state) {
        return (p.features || []).filter(function (f) { return f.state === state; }).length;
      })]));
    } else lines.push(tableOf("project completion", ["done", "total", "completion", "an agent is on it", "to do"],
      [[done, total, completionPercent(done, total) + "%", active, total - done - active]]));
    if (p.reason) line(p.reason);
    (p.features || []).forEach(function (feature) {
      line(itemLabel(feature) + " · " + feature.done + " / " + feature.total);
      if (feature.stages) {
        line(sourceName(p) + " · " + feature.state);
        if (feature.status_hint) line("status line says " + feature.status_hint);
        if (feature.status_mark) line(feature.status_mark === "status-not-updated" ? "status not updated" : "accepted");
        feature.stages.forEach(function (row) { line(row.stage + " · " + row.state + " · " + row.done + "/" + row.total); });
        (feature.packages || []).forEach(function (pkg) { line("package " + pkg.ordinal + " · " + pkg.state); });
        if (feature.review_counts) ["code", "security"].forEach(function (kind) {
          line(kind + " review artefacts · " + feature.review_counts[kind] + " · final " + (feature.review_counts[kind + "_final"] ? "present" : "absent"));
        });
      }
      [ ["phases", "phase", "Phase "], ["stories", "story", ""] ].forEach(function (group) {
        (feature[group[0]] || []).forEach(function (row) {
          line(group[2] + row[group[1]] + (row.priority ? " · P" + row.priority : "") + " · " + row.done + " / " + row.total);

        });
      });
      var table = h("table", "tbl"), head = h("tr");
      ["Task", "Story", "Phase", "State", "Agent / model", "Session / host", "Run / elapsed"].forEach(function (name) {
        var cell = h("th"); cell.textContent = name; head.appendChild(cell);
      });
      table.appendChild(head);
      (feature.tasks || []).forEach(function (task) {
        var row = h("tr"), runs = task.runs || [], sessions = task.sessions || [];
        [task.id || "checkbox", task.story || "—", task.phase == null ? "—" : task.phase, task.state,
          runs.map(function (run) { return run.agent + " / " + run.model; }).join(", ") || "—",
          sessions.map(function (session) { return session.id + " / " + session.host; }).join(", ") || "—",
          runs.map(function (run) { return run.id + " / " + run.elapsed_seconds + " seconds · " + run.outcome; }).join(", ") || "—"].forEach(function (value) {
            var cell = h("td"); cell.textContent = value; row.appendChild(cell);
          });
        table.appendChild(row);
      });
      var wrap = h("div", "project-table"); wrap.appendChild(table); lines.push(wrap);
    });
    if (p.work && Object.keys(p.work).length) line("ledger work · latest task outcomes · " + Object.keys(p.work).map(function (state) { return state + ": " + p.work[state]; }).join(" · "));
    var counts = p.sessions || {};
    line("Sessions · running now: " + (p.running_now == null ? "unavailable" : p.running_now) + " (machine-wide process count, not identified sessions) · active in the last 24 hours: " + (counts.active_24h || 0) + " · idle: " + (counts.idle || 0));
    line("Delegated runs · " + Object.keys(p.outcomes || {}).map(function (kind) { return kind + ": " + p.outcomes[kind]; }).join(" · "));
    line("label without a feature: " + (p.labels_without_feature || 0) + " · unlinked runs: " + (p.unlinked_runs || 0));
    line("Sessions without a task");
    (p.sessions_without_task || []).forEach(function (session) { line(session.id + " · " + session.host + " · last activity " + session.last); });
    line("Last reviews · " + Object.keys(p.reviews || {}).map(function (kind) { return kind + ": " + p.reviews[kind]; }).join(" · ") + " · manifest " + (p.version || "unknown"));
    if (p.work_records && p.work_records.skipped) line("Work records skipped: " + p.work_records.skipped);
    (p.skipped || []).forEach(function (reason) { line(reason); });
    return stack(lines);
  }
  function repoLabel(code) {
    var repos = D.progress && D.progress.repositories || {}, key = String(code).replace(/^repo-/, "");
    var project = Object.prototype.hasOwnProperty.call(repos, key) ? repos[key] : null;
    return project && project.label || "repo " + key.slice(0, 4);
  }
  function storyPriority(story) { return story.priority >= 1 && story.priority <= 9 ? story.priority : 10; }
  function unfinishedFeatures(p) { return (p.features || []).filter(function (f) { return f.state ? f.state !== "done" : f.total > f.done; }); }
  function taskOrder(a, b) {
    return (a.phase == null ? 100 : a.phase) - (b.phase == null ? 100 : b.phase) || String(a.id).localeCompare(String(b.id), undefined, {numeric: true});
  }
  function storyOrder(a, b) {
    return storyPriority(a) - storyPriority(b) || String(a.story).localeCompare(String(b.story), undefined, {numeric: true});
  }
  function taskState(task) {
    return task.state === "done" ? "done" : task.state === "in progress" ? "active" : task.state === "accepted, not ticked" ? "accepted" : "todo";
  }
  function taskLegend() {
    var legend = h("div", "task-legend");
    [["done", "done"], ["active", "agent on it"], ["accepted", "done, not accepted"], ["todo", "to do"]].forEach(function (item) {
      legend.appendChild(h("span", "legend-item", [brick(item[0], 15, 8, "legend-brick"), t("span", "", item[1])]));
    });
    return legend;
  }
  function completionPercent(done, total) {
    return total ? Math.min(done === total ? 100 : 99, Math.floor(done / total * 100)) : 0;
  }
  function namedActivity(block) {
    return (Array.isArray(block.active) ? block.active : []).filter(function (row) {
      return row && typeof row.label === "string" && row.label.trim();
    }).sort(function (a, b) {
      return activityTime(b.last) - activityTime(a.last) || String(a.repo).localeCompare(String(b.repo));
    }).slice(0, 12);
  }
  function activityTime(value) {
    var at = Date.parse(typeof value === "string" ? value : "");
    return Number.isFinite(at) ? at : 0;
  }
  function activityHosts(value) {
    return (Array.isArray(value) ? value : []).map(String).filter(function (host, index, all) {
      return ["claude", "codex", "antigravity"].indexOf(host) !== -1 && all.indexOf(host) === index;
    });
  }
  function activeProjects(block) {
    var rows = namedActivity(block), list = h("div", "active-projects"), motion = {index: 0};
    if (!rows.length) list.appendChild(t("div", "meta", "No named project active in the last 24 hours. Run fnl-status inside a repository to add it."));
    rows.forEach(function (project) {
      var hosts = h("span", "active-hosts");
      activityHosts(project.hosts).forEach(function (host) {
        var shape = {claude: "●", codex: "◆", antigravity: "▲"}[host];
        hosts.appendChild(tipOn(t("span", "active-host", shape), {title: host, sub: "project total · 24h", rows: [["sessions", project.sessions]]}));
      });
      var at = activityTime(project.last), age = Math.max(0, Math.floor((Date.now() - at) / 60000));
      var last = age < 60 ? age + " min" : age < 1440 ? Math.floor(age / 60) + " hr" : Math.floor(age / 1440) + " d";
      var snapshot = (block.repositories || {})[project.repo] || {}, unfinished = unfinishedFeatures(snapshot).length > 0;
      var hasTasks = (snapshot.features || []).some(function (feature) { return feature.total > 0; });
      var pipeline = (snapshot.features || []).some(function (feature) { return Array.isArray(feature.stages); });
      var label = tipOn(t("strong", "active-label", project.label), project.label);
      var row = h("div", "active-project", [h("div", "active-identity", [label,
        h("div", "active-meta", [hosts, t("span", "active-last", at ? "last " + last + " ago" : "last unavailable")])])]);
      row.setAttribute("data-repo", project.repo);
      if (pipeline) row.className += " pipeline-project";
      tipOn(row, pipeline || !hasTasks ? sourceTip(snapshot, project.label) : project.label + " · " + (at ? String(project.last) : "last unavailable"));
      var percent = Number(project.percent), percentCell;
      if (hasTasks && !unfinished) {
        percentCell = brick("done", 22, 14, "project-done");
        percentCell.setAttribute("aria-hidden", "false"); percentCell.setAttribute("role", "img");
        percentCell.setAttribute("aria-label", "done");
        percentCell.appendChild(s("path", {d: "M6 10l3 3 7-6", fill: "none", stroke: "var(--bg)", "stroke-width": 2,
          "stroke-linecap": "round", "stroke-linejoin": "round", "class": "done-check"}));
      } else {
        percentCell = t("span", "active-percent", "");
        if (!pipeline && project.percent != null && Number.isFinite(percent))
          percentCell.textContent = Math.max(0, Math.min(99, Math.floor(percent))) + "%";
      }
      row.appendChild(pipeline ? pipelineDetail(snapshot, motion) : projectDetail(snapshot, motion)); row.appendChild(percentCell);
      list.appendChild(row);
    });
    list.appendChild(taskLegend());
    TABS.get("now").tableRows.push(tableOf("active projects", ["project", "hosts", "sessions · 24h", "last", "done"], rows.map(function (row) {
      var percent = Number(row.percent);
      return [row.label, activityHosts(row.hosts).join(", "), row.sessions, activityTime(row.last) ? String(row.last) : "unavailable",
        row.percent == null || !Number.isFinite(percent) ? "—" : Math.max(0, Math.min(100, Math.floor(percent))) + "%"];
    })));
    return list;
  }
  function taskTip(group, feature, story) {
    if (group.length > 1) {
      return {title: (group[0].id || "checkbox") + " to " + (group[group.length - 1].id || "checkbox"),
        rows: [["done", "done"], ["agent on it", "active"], ["not accepted", "accepted"], ["to do", "todo"]].map(function (row) {
          return [row[0], group.filter(function (task) { return taskState(task) === row[1]; }).length];
        })};
    }
    var task = group[0], runs = task.runs || [], sessions = task.sessions || [], state = taskState(task);
    return {title: task.id || "checkbox", sub: (story || "no story tag") + " · spec " + String(feature == null ? "—" : feature).padStart(3, "0"),
      rows: [["agent / model", runs.map(function (run) { return run.agent + " / " + run.model; }).join(", ") || "—"],
        ["session / host", sessions.map(function (session) { return session.id + " / " + session.host; }).join(", ") || "—"]],
      chips: [{label: {done: "done", active: "agent on it", accepted: "not accepted", todo: "to do"}[state], state: state}]};
  }
  function sourceName(p) {
    return p.source === "speckit" ? "Spec Kit" : p.source === "ledger" ? "ledger" :
      p.source === "work-record" ? "work records" : p.source === "checkbox" ? "configured checkboxes" : p.source && p.source !== "none" ?
      p.source + (p.recognition === "index" ? " index" : " status lines") : "no recognised pipeline";
  }
  function sourceTip(p, title) {
    var items = p.source && p.source !== "none" ? ["Artefact presence is evidence of a stage, not a review verdict or release proof."] :
      ["no task list · Looked for Spec Kit specs/NNN-name, work records, configured checkboxes, docs/specs, docs/spec and specs indexes/status lines, release packages, and exact-project ledger runs."];
    if (p.ledger_join === "none") items.push("No ledger source: no Ledger project override and no runs match the folder name.");
    if (p.ledger_join === "configured-empty") items.push("No ledger source: no runs match the configured Ledger project.");
    if (p.work_records && p.work_records.skipped) items.push("Work records skipped: " + p.work_records.skipped);
    if (p.reason) items.push(p.reason);
    return {title: title, sub: sourceName(p), items: items.concat(p.skipped || []).slice(0, 5)};
  }
  function itemLabel(f) {
    return f.feature != null ? "spec " + String(f.feature).padStart(3, "0") : "item " + f.ordinal;
  }
  function stageTip(p, f, row) {
    var items = [];
    if (f.status_hint) items.push("status line says " + f.status_hint);
    if (row.state === "unknown") items.push("no status stated");
    if (row.stage !== "tasks" && row.stage !== "packages" && row.stage !== "work") items.push("Artefact present; no content or verdict inferred.");
    var rows = [["item state", f.state], ["stage state", row.state], ["done / total", row.done + " / " + row.total]];
    if (row.stage === "tasks") {
      (f.stories || []).slice().sort(storyOrder).forEach(function (story) {
        rows.push([story.story + (story.priority ? " · P" + story.priority : ""), story.done + " / " + story.total]);
      });
      if (f.total && f.done === f.total && f.artifacts && !f.artifacts.verify) items.push("All tasks checked; verify artefact absent.");
    }
    return {title: itemLabel(f) + " · " + row.stage, sub: sourceName(p), rows: rows, items: items};
  }
  function progressSegments(f) {
    var svg = s("svg", {width: 42, height: 3, viewBox: "0 0 42 3", "class": "pipeline-progress", "aria-hidden": "true"});
    var id = "pipeline-clip-" + (++brickId), defs = s("defs"), clip = s("clipPath", {id: id});
    clip.appendChild(s("rect", {width: 42, height: 3, rx: 1.5})); defs.appendChild(clip); svg.appendChild(defs);
    var group = s("g", {"clip-path": "url(#" + id + ")", "shape-rendering": "crispEdges"});
    var counts = {done: 0, active: 0, accepted: 0, todo: 0};
    (f.tasks || []).forEach(function (task) { counts[taskState(task)]++; });
    var offset = 0, total = Math.max(1, f.total);
    ["done", "active", "accepted", "todo"].forEach(function (state) {
      var width = counts[state] / total * 42;
      if (width) group.appendChild(s("rect", {x: offset, y: 0, width: width, height: 3,
        fill: {done: "var(--h2)", active: "var(--p)", accepted: "var(--warn)", todo: "var(--line)"}[state], "class": "pipeline-segment " + state}));
      offset += width;
    });
    svg.appendChild(group); return svg;
  }
  function pipelineText(cls, value) { var el = h("span", cls); el.textContent = String(value); return el; }
  function pipelineIcon(kind) {
    var icon = s("svg", {width: 12, height: 12, viewBox: "0 0 16 16", "class": "pipeline-icon pipeline-icon-" + kind, "aria-hidden": "true"});
    icon.appendChild(s("path", {d: {code: "M5 4L1 8L5 12M11 4L15 8L11 12M9.5 2L6.5 14",
      security: "M8 1L14 3V7C14 11 11 14 8 15C5 14 2 11 2 7V3Z", run: "M4 2L13 8L4 14Z"}[kind],
      fill: "none", stroke: "currentColor", "stroke-width": 1.5, "stroke-linejoin": "round", "stroke-linecap": "round"}));
    return icon;
  }
  function pipelineBlock(p, f, row) {
    var block = h("span", "pipeline-block " + row.state);
    block.setAttribute("data-stage", row.stage); block.setAttribute("data-state", row.state);
    var shape = s("svg", {viewBox: "0 0 64 24", preserveAspectRatio: "none", "class": "pipeline-chevron", "aria-hidden": "true"});
    var face = s("path", {d: "M1 1H56L63 12L56 23H1L8 12Z", fill: "var(--raised)", "class": "pipeline-face", "vector-effect": "non-scaling-stroke"});
    if (row.state === "active") {
      var id = "pipeline-hatch-" + (++brickId), defs = s("defs"), pattern = s("pattern", {
        id: id, width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)"});
      pattern.appendChild(s("rect", {width: 2, height: 4, fill: "var(--p)"}));
      defs.appendChild(pattern); shape.appendChild(defs); face.setAttribute("fill", "url(#" + id + ")");
    }
    shape.appendChild(face); block.appendChild(shape);
    if (row.stage === "review") {
      var reviews = f.review_counts || {};
      ["code", "security"].forEach(function (kind) {
        var chip = h("span", "pipeline-review " + (reviews[kind] ? "done" : "unknown"), [pipelineIcon(kind)]);
        chip.setAttribute("data-review", kind);
        if (reviews[kind + "_final"]) chip.appendChild(pipelineText("review-final", "✓"));
        tipOn(chip, {title: kind + " review artefacts", sub: sourceName(p), rows: [["files", reviews[kind] || 0], ["final", reviews[kind + "_final"] ? "present" : "absent"]],
          items: ["File presence only; no approval inferred."]});
        block.appendChild(chip);
      });
    } else {
      var label = h("span", "pipeline-label", [pipelineText("pipeline-stage-label", row.stage)]);
      block.appendChild(label);
      if (row.stage === "tasks") {
        label.appendChild(pipelineText("pipeline-percent", completionPercent(row.done, row.total) + "%"));
        block.appendChild(progressSegments(f));
      }
    }
    return tipOn(block, stageTip(p, f, row));
  }
  function workStrip(p) {
    var strip = h("div", "work-strip"), counts = p.work || {};
    strip.appendChild(pipelineIcon("run"));
    var summary = "ledger runs: " + (counts.done || 0) + " accepted, " + (counts["needs-attention"] || 0) + " need attention";
    var items = ["Exact project join; repeated task labels share their latest outcome."];
    tipOn(strip, {title: summary, rows: ["active", "deferred", "unknown"].filter(function (state) { return counts[state]; }).map(function (state) {
      return [state, counts[state]];
    }), items: items});
    ["done", "needs-attention", "active", "deferred", "unknown"].forEach(function (state) {
      if (!counts[state]) return;
      var chip = pipelineText("work-chip " + state, String(counts[state]));
      tipOn(chip, {title: summary, sub: state, rows: [["latest task outcomes", counts[state]]],
        items: items.concat(state === "unknown" ? ["no status stated"] : [])}); strip.appendChild(chip);
    });
    return strip;
  }
  function pipelineDetail(p, motion) {
    var card = h("div", "project-detail pipeline-detail"), unfinished = unfinishedFeatures(p).slice().sort(function (a, b) {
      return (b.feature || b.ordinal || 0) - (a.feature || a.ordinal || 0);
    });
    var finished = (p.features || []).length - unfinished.length, taskItem = null;
    if (p.source !== "ledger") unfinished.slice(0, 5).forEach(function (feature) {
      var line = h("div", "pipeline-item", [tipOn(pipelineText("pipeline-ordinal", feature.feature != null ? String(feature.feature).padStart(3, "0") : "#" + feature.ordinal),
        {title: itemLabel(feature), sub: sourceName(p), rows: [["state", feature.state]], items: feature.status_hint ? ["status line says " + feature.status_hint] : []})]);
      var chain = h("div", "pipeline-chain");
      (feature.stages || []).forEach(function (row) { chain.appendChild(pipelineBlock(p, feature, row)); });
      if (feature.status_mark) {
        var statusMark = h("span", "pipeline-status-mark " + feature.status_mark);
        statusMark.setAttribute("role", "img");
        statusMark.setAttribute("aria-label", feature.status_mark === "status-not-updated" ? "status not updated" : "accepted");
        tipOn(statusMark, {title: feature.status_mark === "status-not-updated" ? "status not updated" : "accepted",
          items: feature.status_mark === "status-not-updated" ? ["All tasks checked; Status still in progress."] : ["Status accepted; work remains to do."]});
        chain.appendChild(statusMark);
      }
      line.appendChild(chain);
      (feature.packages || []).forEach(function (pkg) {
        var mark = brick(pkg.state === "done" ? "done" : pkg.state === "active" ? "active" : "todo", 12, 7, "package-brick " + pkg.state);
        tipOn(mark, {title: "package " + pkg.ordinal, sub: sourceName(p), rows: [["state", pkg.state]], items: pkg.state === "unknown" ? ["no status stated"] : []});
        mark.setAttribute("aria-hidden", "false"); mark.setAttribute("role", "img"); line.appendChild(mark);
      });
      if (!taskItem && feature.state === "active" && (feature.tasks || []).length) { taskItem = feature; line.appendChild(projectDetail({features: [feature]}, motion, true)); }
      card.appendChild(line);
    });
    if (p.source !== "ledger" && unfinished.length > 5) card.appendChild(tipOn(pipelineText("pipeline-more", "+" + (unfinished.length - 5)),
      {title: sourceName(p), rows: [["unfinished items", unfinished.length]], items: unfinished.slice(5, 10).map(function (f) { return itemLabel(f) + " · " + f.state; })}));
    if (p.source !== "ledger" && finished) card.appendChild(tipOn(pipelineText("pipeline-finished", "✓ " + finished),
      {title: sourceName(p), rows: [["finished items", finished]], items: (p.features || []).filter(function (f) { return f.state === "done"; }).slice(-5).reverse().map(function (f) { return itemLabel(f) + " · done" + (f.status_hint ? " · status line says " + f.status_hint : ""); })}));
    if (Object.keys(p.work || {}).length) card.appendChild(workStrip(p));
    return card;
  }
  function projectDetail(p, motion, pipeline) {
    var card = h("div", pipeline ? "pipeline-tasks" : "project-detail");
    unfinishedFeatures(p).forEach(function (feature) {
      var tasks = feature.tasks || [], stories = (feature.stories || []).slice();
      if (tasks.some(function (task) { return !task.story; })) {
        var untagged = tasks.filter(function (task) { return !task.story; });
        stories.push({story: null, priority: null, total: untagged.length, done: untagged.filter(function (task) { return task.state === "done"; }).length});
      }
      var complete = stories.filter(function (story) { return story.total > 0 && story.done === story.total; }).length;
      var header = h("div", "spec-head", [t("span", "spec-label", "spec " + String(feature.feature).padStart(3, "0")), h("i", "spec-rule")]);
      if (complete) header.appendChild(t("span", "finished-stories", "+" + complete + " done"));
      var featureBody = h("div", "feature", pipeline ? [] : [header]);
      stories.filter(function (story) { return story.total > story.done; }).sort(storyOrder).forEach(function (story) {
        var cells = h("div", "cells"), sorted = tasks.filter(function (task) { return (task.story || null) === (story.story || null); }).sort(taskOrder);
        var per = Math.max(1, Math.ceil(sorted.length / 36));
        for (var i = 0; i < sorted.length; i += per) {
          var group = sorted.slice(i, i + per), states = group.map(taskState);
          var state = states.indexOf("active") !== -1 ? "active" : states.indexOf("accepted") !== -1 ? "accepted" :
            states.every(function (x) { return x === "done"; }) ? "done" : "todo";
          var mark = brick(state, 15, 8, "task-brick");
          mark.setAttribute("data-task", group[0].id || "checkbox"); mark.setAttribute("data-state", state); mark.setAttribute("data-count", group.length);
          mark.style.setProperty("--snap-delay", Math.min(500, motion.index++ * 10) + "ms");
          tipOn(mark, taskTip(group, feature.feature, story.story));
          mark.setAttribute("aria-hidden", "false"); mark.setAttribute("role", "img");
          cells.appendChild(mark);
        }
        var label = t("span", "story-label", story.story || "");
        if (!story.story) {
          var icon = s("svg", {width: 14, height: 14, viewBox: "0 0 16 16", "class": "story-no-tag", role: "img"});
          icon.appendChild(s("path", {d: "M2 2H8L14 8L8 14L2 8Z", fill: "none", stroke: "currentColor", "stroke-width": 1, "stroke-dasharray": "2 2", "stroke-linejoin": "round"}));
          icon.appendChild(s("circle", {cx: 5, cy: 5, r: 1, fill: "currentColor"}));
          label.appendChild(tipOn(icon, {title: "no story tag", rows: [["done / total", story.done + " / " + story.total]],
            items: [completionPercent(story.done, story.total) + "% done"]}));
        }
        var row = h("div", "story", [label, cells, t("span", "story-count", story.done + "/" + story.total)]);
        row.setAttribute("data-story", story.story || "untagged");
        tipOn(row, story.done + "/" + story.total + " · " + completionPercent(story.done, story.total) + "% done" + (storyPriority(story) < 10 ? " · P" + story.priority : ""));
        featureBody.appendChild(row);
      });
      card.appendChild(featureBody);
    });
    return card;
  }
  function projectPanel() {
    if (!D.progress) return null;
    var block = D.progress, repositories = block.repositories || {};
    var activeNames = {};
    namedActivity(block).forEach(function (row) { activeNames[row.repo] = row.label; });
    var keys = Object.keys(repositories).filter(function (code) { return repositories[code].label || activeNames[code]; });
    var content = [activeProjects(block)];
    keys.forEach(function (code) {
      TABS.get("now").tableRows.push(h("div", "tbl", [t("h3", "", repositories[code].label || activeNames[code]), projectData(repositories[code])]));
    });
    return stack(content);
  }
  function projectLimits() {
    return {title: "How to read this", items: [
      "Named projects show local activity in the last 24 hours.",
      "Pipelines show recognised artefacts or repository states; small bricks show tasks or packages.",
      "Task done means ticked; not accepted remains unfinished. Features need verify artefacts.",
      "At most five unfinished items; finished items collapse into a count. Tables keep details.",
      "Links use recorded task ids and runs; unlinked sessions stay separate."
    ]};
  }
  function signed(n) { return (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n); }

  /* Charts */
  function sparkColumns(arr, label) {
    var mx = Math.max.apply(null, arr.filter(function (v) { return v != null; })) || 1;
    return h("div", "spark", arr.map(function (v, i) {
      var c = h("i"), where = label + ", week " + (i + 1) + " of " + arr.length + ": ";
      if (v == null) { c.className = "gap"; c.style.height = "3px"; return tipOn(c, where + "no data"); }
      c.style.height = Math.max(6, v / mx * 100) + "%";
      return tipOn(c, where + (label.indexOf("%") > -1 ? pct(v) : v));
    }));
  }
  function ghostSpark() {
    var heights = [40, 62, 48, 80, 56, 70, 44, 88, 60, 52, 74, 66];
    return h("div", "spark", heights.map(function (v) { var c = h("i", "ghost"); c.style.height = v + "%"; return c; }));
  }
  function hbars(rows, color) {
    var mx = Math.max.apply(null, rows.map(function (r) { return r.v; })) || 1;
    return h("div", "hb", rows.map(function (r) {
      var f = h("i"); f.style.width = (r.v / mx * 100) + "%"; f.style.background = color;
      return tipOn(h("div", "r", [t("span", "n", r.n), h("span", "trk", [f, t("span", "v", r.label || r.v)])]), r.tip || (r.n + ": " + r.v));
    }));
  }
  /* The plugin icon (assets/icon.svg): a winking robot face between code brackets. */
  function brandMark() {
    var svg = s("svg", { viewBox: "0 0 128 128", role: "img", "aria-label": "Finolabs Vibecode" });
    var stroke = { fill: "none", stroke: "currentColor", "stroke-width": 9, "stroke-linecap": "round" };
    svg.appendChild(s("path", Object.assign({ d: "M30 36 L10 64 L30 92 M98 36 L118 64 L98 92", "stroke-linejoin": "round" }, stroke)));
    svg.appendChild(s("rect", { x: 36, y: 54, width: 20, height: 20, rx: 4, fill: "currentColor" }));
    svg.appendChild(s("path", Object.assign({ d: "M72 64 H92" }, stroke)));
    return svg;
  }
  function tableOf(title, head, rows) {
    return h("div", "tbl", [t("h3", "", title), h("table", "", [
      h("thead", "", [h("tr", "", head.map(function (c, i) { return t("th", i ? "r" : "", c); }))]),
      h("tbody", "", rows.map(function (r) { return h("tr", "", r.map(function (c, i) { return t("td", i ? "r" : "", c); })); }))])]);
  }

  /* draw() builds the whole page from D, so a newer data.js can replace it in place; the month shown and the open tables stay. */
  var month = null, footer = null, updatedEl = null, statusDot = null, footerInfo = null;
  /* Only these literal names can select a panel or become a fragment. */
  var TABS = new Map([
    ["overview", { label: "Overview", id: "panel-overview", buttonId: "tab-overview" }],
    ["now", { label: "Now", id: "panel-now", buttonId: "tab-now" }]
  ]);
  var TAB_LINKS = new Map([["overview", "overview"], ["now", "now"],
    ["agents", "now"], ["project", "now"], ["delegation", "overview"], ["reviews", "overview"]]);
  function resolveTab(value) { return TAB_LINKS.get(value) || "overview"; }
  var selected = "overview";
  function hashTab() { return window.location.hash.slice(1); }
  function initialTab() {
    if (window.location.hash) return resolveTab(hashTab());
    try { var value = localStorage.getItem("fnl-tab"); if (TAB_LINKS.has(value)) return resolveTab(value); } catch (e) { /* storage can be blocked */ }
    return "overview";
  }
  selected = initialTab();
  function selectTab(name, remember) {
    selected = resolveTab(name);
    TABS.forEach(function (tab, key) {
      var active = key === selected;
      tab.button.setAttribute("aria-selected", String(active));
      tab.button.tabIndex = active ? 0 : -1;
      if (!tab.panel.hidden) { tab.scrollTop = tab.panel.scrollTop; tab.scrollLeft = tab.panel.scrollLeft; }
      if (!active) tab.panel.setAttribute("data-enter", "false");
      else if (tab.panel.hidden) {
        tab.panel.setAttribute("data-enter", String(!!tab.pendingAnimation)); tab.pendingAnimation = false;
      }
      tab.panel.hidden = !active;
      if (active) { tab.panel.scrollTop = tab.scrollTop || 0; tab.panel.scrollLeft = tab.scrollLeft || 0; }
    });
    closeTip();
    placeFooter();
    try { localStorage.setItem("fnl-tab", selected); } catch (e) { /* storage can be blocked */ }
    if (remember) {
      if (hashTab() !== selected) window.location.hash = selected;
    }
  }
  window.addEventListener("hashchange", function () { selectTab(hashTab(), false); });
  function drawTabs() {
    var strip = document.getElementById("tabs"), names = Array.from(TABS.keys());
    strip.replaceChildren();
    strip.setAttribute("role", "tablist"); strip.setAttribute("aria-label", "Dashboard sections");
    TABS.forEach(function (tab, name) {
      var button = t("button", "", tab.label), panel = h("div", "tabpanel");
      button.type = "button";
      button.setAttribute("role", "tab"); button.setAttribute("id", tab.buttonId);
      button.setAttribute("aria-controls", tab.id);
      panel.setAttribute("role", "tabpanel"); panel.setAttribute("id", tab.id);
      panel.setAttribute("aria-labelledby", tab.buttonId); panel.tabIndex = 0; panel.hidden = true;
      var count = null;
      if (name === "now" && (D.running || D.progress))
        count = (D.running ? (D.running.open || []).length : 0) + (D.progress ? namedActivity(D.progress).length : 0);
      if (count != null) { var badge = h("span", "count"); badge.textContent = String(count); button.appendChild(badge); }
      button.addEventListener("click", function () { selectTab(name, true); });
      button.addEventListener("keydown", function (e) {
        var index = names.indexOf(name), target = null;
        if (e.key === "ArrowRight") target = names[(index + 1) % names.length];
        if (e.key === "ArrowLeft") target = names[(index + names.length - 1) % names.length];
        if (e.key === "Home") target = names[0];
        if (e.key === "End") target = names[names.length - 1];
        if (target !== null) {
          e.preventDefault();
          TABS.forEach(function (tab, key) { tab.button.tabIndex = key === target ? 0 : -1; });
          TABS.get(target).button.focus();
        } else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectTab(name, true); }
      });
      var signature = name === "now" ? JSON.stringify([D.running, D.progress]) : "";
      if (signature !== tab.signature) tab.pendingAnimation = true;
      tab.signature = signature;
      tab.button = button; tab.panel = panel; tab.tableRows = [];
      strip.appendChild(button);
    });
    TABS.forEach(function (tab) { app.appendChild(tab.panel); });
  }
  function placeFooter() {
    var tab = TABS.get(selected);
    if (footer && tab.panel) tab.panel.insertBefore(footer, tab.tables || null);
  }
  function updateFreshness() {
    if (!footerInfo) return;
    var f = D.freshness || {}, now = Date.now(), builtAge = (now - Date.parse(f.built_at)) / 1000;
    var elapsed = Number.isFinite(builtAge) ? Math.max(0, builtAge) : 0;
    function minutes(seconds) { var n = Math.floor(seconds / 60); return n + (n === 1 ? " minute" : " minutes"); }
    function age(value) {
      return value == null ? "no reading" : typeof value === "number" ? minutes(value + elapsed) + " old" : String(value);
    }
    var hosts = f.latest_event || {}, names = {claude: "Claude Code", codex: "Codex", antigravity: "Antigravity"};
    var sess = D.sessions || {}, staleHost = false;
    var lines = ["sources " + (D.sources || []).map(function (source) {
      return source.name + (source.ok ? "" : " (unavailable)") + (source.note ? ": " + source.note : "");
    }).join(" · "),
      "sessions " + num(sess.total) + " · with edits " + num(sess.with_edits) + " · unclassified " + num(sess.unclassified) +
      " · writer errors " + num(D.errors) + " · generated " + (D.generated || "—"), "built " + (f.built_at || "—")];
    Object.keys(hosts).forEach(function (host) {
      var hostAge = (now - Date.parse(hosts[host])) / 1000;
      var quiet = hostAge > 900;
      if (quiet && Number.isFinite(hostAge)) staleHost = true;
      var otherActive = Object.keys(hosts).some(function (other) {
        return other !== host && (now - Date.parse(hosts[other])) / 1000 <= 900;
      });
      lines.push((Object.prototype.hasOwnProperty.call(names, host) ? names[host] : host) + ": last event " + hosts[host] +
                 (quiet && otherActive ? "; hooks may need trust" : ""));
    });
    lines.push("ledger: " + age(f.ledger_age_seconds), "quota: " + age(f.quota_age_seconds));
    if (builtAge > 60 && document.visibilityState === "visible")
      lines.push("data is " + minutes(builtAge) + " old; it updates while a session runs tools");
    var generatedAge = (now - Date.parse(D.generated)) / 60000;
    var n = Math.max(0, Math.floor(generatedAge));
    var relative = n < 60 ? n + " min" : n < 1440 ? Math.floor(n / 60) + " hr" : Math.floor(n / 1440) + " d";
    updatedEl.textContent = Number.isFinite(generatedAge) ? "updated " + relative + " ago" : "updated time unknown";
    var state = generatedAge > 360 ? "stale" : !Number.isFinite(generatedAge) || generatedAge > 10 || staleHost ? "quiet" : "fresh";
    statusDot.setAttribute("data-state", state);
    statusDot.setAttribute("aria-label", state === "stale" ? "page data stale" : state === "quiet" ? "data or host activity quiet" : "data fresh");
    tipOn(footerInfo, lines.join("\n"));
    if (tipAnchor === footerInfo && !tip.hidden) renderTip(tips.get(footerInfo));
  }
  function draw() {
  var focusedTab = null;
  TABS.forEach(function (tab) {
    if (tab.button === document.activeElement) focusedTab = tab;
    if (tab.panel && !tab.panel.hidden) { tab.scrollTop = tab.panel.scrollTop; tab.scrollLeft = tab.panel.scrollLeft; }
    if (tab.tables) tab.tablesOpen = tab.tables.open;
    tab.tables = null;
  });
  closeTip(); footer = null; footerInfo = null;
  app.replaceChildren();
  document.querySelector(".win").classList.toggle("skel", !D);
  var emptyNotice = null;
  if (!D) {
    D = { missing: {}, sources: [] };
    ["activity", "router", "use", "load", "depth", "reviews", "delegation"].forEach(function (key) { D.missing[key] = "no data yet"; });
    emptyNotice = h("div", "veil", [h("div", "notice", [h("div", "badge", [brandMark()]), t("strong", "", "No data yet"),
      t("span", "", "Run fnl-status to build this page from your usage events and dispatch ledger."),
      t("span", "", "Usage events need your consent in fnl-setup and a session started after it.")])]);
  }

  var sess = D.sessions || {}, k = D.kpi || {}, sp = k.spark || {};
  app.appendChild(tipOn(h("div", "cmd", [
    t("span", "ps", "$"), t("span", "", "fnl-status" + (D.period ? " --since " + D.period.days + "d" : "")), h("span", "cursor"),
    t("span", "meta", D.period ? D.period.from + " → " + D.period.to : "")
  ]), {title: "~/finolabs-vibecode — fnl-status", items: ["Local usage metadata and dispatch ledger."]}));
  if (emptyNotice) app.appendChild(emptyNotice);

  /* KPI strip */
  var kp = h("div", "kpis");
  [["Router coverage", pct(k.router_coverage), sp.router_coverage, "router coverage %", true],
   ["Sessions", num(k.sessions), sp.sessions, "sessions", false],
   ["Skill and agent calls", num(k.calls), sp.calls, "calls", false],
   ["Delegation first pass", pct(k.first_pass), sp.first_pass, "first pass %", true]].forEach(function (x) {
    var a = x[2], d = null, dc = "d";
    if (a && a.length > 1 && a[a.length - 1] != null && a[a.length - 2] != null) {
      var diff = a[a.length - 1] - a[a.length - 2], n = x[4] ? Math.round(diff * 100) : Math.round(diff);
      d = signed(n) + (x[4] ? " pts" : "") + " vs last week";
      if (x[4] && n) dc += n > 0 ? " up" : " down";
    }
    kp.appendChild(h("div", "kpi", [t("div", "k", x[0]), h("div", "m", [t("div", "v", x[1]), a ? sparkColumns(a, x[3]) : ghostSpark()]), t("div", dc, d || "")]));
  });
  app.appendChild(kp);

  drawTabs();
  var overview = TABS.get("overview").panel;
  TABS.get("now").panel.appendChild(pane("running now", infoButton(runningLimits() || "not available yet"), "", runningPanel(), "not available yet"));
  TABS.get("now").panel.appendChild(pane("projects, last 24 h", infoButton(projectLimits()), "", projectPanel(), "not available yet"));

  /* Overview: activity and router composition beside depth and load cost. */
  var band1 = h("div", "g2");
  var act = D.activity || [], cal = null;
  if (act.length) {
    var byDate = {}, months = [], amax = 1;
    act.forEach(function (a) {
      byDate[a.date] = a.count; if (a.count > amax) amax = a.count;
      var ym = a.date.slice(0, 7); if (months.indexOf(ym) < 0) months.push(ym);
    });
    var MONTH = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    var WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], lastDay = act[act.length - 1].date, cur = months.indexOf(month);
    if (cur < 0) cur = months.length - 1;
    var prev = t("button", "", "‹"), next = t("button", "", "›"), ttl = t("strong", "", ""), side = h("div", "calside"), cg = h("div", "cal");
    prev.type = next.type = "button"; prev.setAttribute("aria-label", "Previous month"); next.setAttribute("aria-label", "Next month");
    var level = function (c) { return c === 0 ? 0 : Math.min(4, 1 + Math.floor(c / amax * 3.999)); };
    var drawCal = function () {
      var ym = months[cur], y = +ym.slice(0, 4), m = +ym.slice(5, 7) - 1, total = 0, best = null, active = 0, inRange = 0, wk = [0, 0, 0, 0, 0, 0, 0];
      var days = new Date(Date.UTC(y, m + 1, 0)).getUTCDate(), lead = (new Date(Date.UTC(y, m, 1)).getUTCDay() + 6) % 7;
      ttl.textContent = MONTH[m] + " " + y;
      while (cg.firstChild) cg.removeChild(cg.firstChild);
      WD.forEach(function (d) { cg.appendChild(t("span", "wd", d)); });
      for (var i = 0; i < lead; i++) cg.appendChild(h("div", "dy pad"));
      for (var d = 1; d <= days; d++) {
        var iso = ym + "-" + (d < 10 ? "0" : "") + d, has = Object.prototype.hasOwnProperty.call(byDate, iso), c = has ? byDate[iso] : null;
        var cell = h("div", "dy" + (has ? "" : " out") + (iso === lastDay ? " now" : ""), [t("span", "", d)]);
        cell.setAttribute("aria-label", iso + (has ? ", " + c + " events" : ", outside the period"));
        if (has) {
          cell.setAttribute("data-l", String(level(c)));
          total += c; inRange++; if (c) active++; wk[(lead + d - 1) % 7] += c; if (c && (!best || c > best[1])) best = [d, c];
          tipOn(cell, iso + ": " + c + " events");
        }
        cg.appendChild(cell);
      }
      for (var p = lead + days; p < 42; p++) cg.appendChild(h("div", "dy pad"));
      while (side.firstChild) side.removeChild(side.firstChild);
      var wmax = Math.max.apply(null, wk), wdc = h("div", "wdc");
      wk.forEach(function (v, i) {
        var bar = h("i", v && v === wmax ? "max" : ""); bar.style.height = Math.max(2, wmax ? v / wmax * 36 : 0) + "px";
        wdc.appendChild(tipOn(h("div", "", [bar, t("em", "", WD[i][0])]), WD[i] + ": " + v + " events"));
      });
      side.appendChild(h("div", "stat2", [t("strong", "", total), t("span", "", "events")]));
      side.appendChild(h("div", "stat2", [t("strong", "", active + "/" + inRange), t("span", "", "days with activity")]));
      side.appendChild(h("div", "stat2", [t("strong", "", best ? MONTH[m].slice(0, 3) + " " + best[0] : "—"), t("span", "", best ? "busiest day, " + best[1] + " events" : "no busiest day")]));
      side.appendChild(h("div", "", [t("div", "cal-title", "events by weekday"), wdc]));
      prev.disabled = cur === 0; next.disabled = cur === months.length - 1;
    };
    prev.addEventListener("click", function () { if (cur > 0) { cur--; month = months[cur]; drawCal(); } });
    next.addEventListener("click", function () { if (cur < months.length - 1) { cur++; month = months[cur]; drawCal(); } });
    var sc = h("div", "scale", [t("span", "", "less")]);
    [0, 1, 2, 3, 4].forEach(function (l) { var q = h("i"); q.style.background = "var(--h" + l + ")"; sc.appendChild(q); });
    sc.appendChild(t("span", "", "more"));
    drawCal();
    cal = h("div", "calwrap", [h("div", "calmain", [h("div", "calnav", [prev, ttl, next]), cg, sc]), side]);
  }
  band1.appendChild(pane("activity", act.length ? "events per day" : "", "tall", cal, missing("activity") || "hooks not installed or consent not given", "cal"));

  var r = D.router, rt = null;
  if (r) {
    var parts = [["covered", r.covered, "var(--good)"], ["missed", r.missed, "var(--crit)"], ["dispatch, excluded", r.excluded, "var(--violet)"], ["unclassified", r.unclassified, "var(--faint)"]];
    var tot = parts.reduce(function (a, p) { return a + p[1]; }, 0) || 1, sg = h("div", "seg"), elig = (r.covered + r.missed) / tot * 100;
    sg.setAttribute("role", "img"); sg.setAttribute("aria-label", parts.map(function (p) { return p[0] + " " + p[1]; }).join(", "));
    parts.filter(function (p) { return p[1] > 0; }).forEach(function (p) { var i = h("i"); i.style.flex = String(p[1]); i.style.background = p[2]; tipOn(i, p[0] + ": " + p[1] + " sessions"); sg.appendChild(i); });
    var brk = h("div", "brk"); brk.style.width = "calc(" + elig + "% - 2px)";
    tipOn(brk, "eligible: " + r.eligible + " sessions with edits. Covered means the router was called before the first edit.");
    rt = stack([sg, brk, t("div", "meta", "eligible " + r.eligible + " · " + pct(r.covered / ((r.covered + r.missed) || 1)) + " covered"),
      legend(parts.map(function (p) { return [p[0] + " " + p[1], p[2]]; }))]);
  }
  var coverageRow = h("div", "g2 coverage-row");
  coverageRow.appendChild(pane("router coverage", "sessions", "", rt, missing("router") || "hooks not installed or consent not given", "stack"));

  var rv = null;
  if (D.reviews && D.reviews.length) {
    var rs = D.review_stats || {total: D.reviews.length,
      reworked: D.reviews.filter(function (x) { return x.verdicts.indexOf("REWORK") !== -1; }).length};
    var rounds = [0, 0, 0];
    D.reviews.forEach(function (x) { if (x.verdicts.length) rounds[Math.min(3, x.verdicts.length) - 1]++; });
    var distribution = h("div", "seg review-distribution");
    distribution.setAttribute("role", "img");
    distribution.setAttribute("aria-label", rounds.map(function (n, i) { return ["1 round", "2 rounds", "3 or more rounds"][i] + ": " + n; }).join(", "));
    rounds.forEach(function (n, i) {
      var part = t("i", "review-round round-" + (i + 1), "");
      part.style.flex = String(n); part.setAttribute("data-count", String(n));
      distribution.appendChild(part);
    });
    var rate = rs.total ? Math.floor((rs.total - rs.reworked) / rs.total * 100) + "%" : "—";
    rv = tipOn(stack([h("div", "stat review-figure", [t("strong", "", rate), t("span", "", "first-pass approve")]),
      distribution, t("div", "meta", "review rounds · 1 / 2 / 3+")]), {
      title: "Review gate", sub: "Last " + Math.min(12, D.reviews.length) + " pull requests · approve teal, rework amber",
      rows: [["first-pass approve", rate], ["pull requests", String(rs.total)],
        ["1 / 2 / 3+ rounds (shown)", rounds.join(" / ")]],
      reviewChains: D.reviews.slice(0, 12).map(function (x) { return x.verdicts; })
    });
    rv.classList.add("review-summary");
  }
  coverageRow.appendChild(pane("review gate", "pull requests", "", rv, missing("reviews") || "no review comments recorded", "rv"));

  band1.appendChild(coverageRow);

  /* Band 2: skill and agent use (tall) beside depth and load cost */
  var band2 = h("div", "g2");
  var use = D.use && D.use.length ? hbars(D.use.map(function (u) { return { n: u.name, v: u.count, tip: u.name + " (" + u.kind + "): " + u.count + " calls" }; }), "var(--p)") : null;
  band2.appendChild(pane("skill and agent use", "calls", "tall", use, missing("use") || "hooks not installed or consent not given", "bars8"));

  var depth = null;
  if (D.depth && D.depth.length) {
    var dmax = Math.max.apply(null, D.depth.map(function (x) { return x.receipts; })) || 1;
    depth = stack([h("div", "hb", D.depth.map(function (x) {
      var clean = h("i"), bad = h("i"), stk = h("span", "stk"), share = x.receipts ? x.reworked / x.receipts : null;
      clean.style.flex = String(x.receipts - x.reworked); clean.style.background = "var(--p)";
      bad.style.flex = String(x.reworked); bad.style.background = "var(--warn)";
      stk.style.width = (x.receipts / dmax * 100) + "%"; stk.appendChild(clean); if (x.reworked) stk.appendChild(bad);
      return tipOn(h("div", "r", [t("span", "n", x.depth), h("span", "trk", [stk, t("span", "v", pct(share))])]),
        x.depth + ": " + x.receipts + " receipts, " + x.reworked + " reworked (indicative, matched by repository and time)");
    })), legend([["clean", "var(--p)"], ["reworked", "var(--warn)"]])]);
  }
  band1.appendChild(pane("depth vs outcome", "indicative", "", depth, missing("depth") || "router receipts not recorded yet", "bars3"));
  overview.appendChild(band1);

  var ld = null;
  if (D.load && D.load.top) {
    ld = hbars(D.load.top.map(function (x) { return { n: x.name, v: x.tokens, label: "~" + tok(x.tokens), tip: x.name + ": ~" + x.tokens + " tokens, loaded " + x.loads + " times (estimate)" }; }), "var(--p)");
  }
  band2.appendChild(pane("load cost", D.load ? "tokens, ~" + tok(D.load.avg_tokens_per_session) + " per session" : "", "", ld, missing("load") || "hooks not installed or consent not given", "bars4"));
  overview.appendChild(band2);

  /* Tables follow their panes; sources and footer stay shared. */
  var tabs = TABS.get("overview").tableRows, delegationTables = tabs;
  if (D.use) tabs.push(tableOf("use", ["name", "calls"], D.use.map(function (u) { return [u.name, u.count]; })));
  if (D.load && D.load.top) tabs.push(tableOf("load (estimate)", ["skill", "tokens", "loads"], D.load.top.map(function (x) { return [x.name, x.tokens, x.loads]; })));
  if (D.depth) tabs.push(tableOf("depth", ["depth", "receipts", "reworked"], D.depth.map(function (x) { return [x.depth, x.receipts, x.reworked]; })));
  if (D.delegation) delegationTables.push(tableOf("delegation", ["agent / model / grade", "runs", "first pass", "quota", "error", "median min", "rework"], D.delegation.map(function (x) { return [x.agent + " / " + x.model + " / " + x.grade, x.runs, pct(x.first_pass), x.quota, x.error, x.median_min, x.rework]; })));
  if (!D.delegation) delegationTables.push(tableOf("delegation", ["status"], [["no data: " + (missing("delegation") || "ledger is empty")]]));
  if (D.kept) delegationTables.push(tableOf("kept and handed off", ["tasks kept", "receipts", "implementation runs handed off"],
    [[D.kept.tasks, D.kept.receipts, num(D.kept.handed_off)]]));
  if (D.kept && D.kept.rows.length) delegationTables.push(tableOf("kept by the coordinator", ["coordinator / reason / settled by", "receipts", "tasks"], D.kept.rows.map(function (x) { return [x.coordinator + " / " + x.reason + " / " + x.route_by, x.receipts, x.tasks]; })));
  if (D.judge) {
    if (!D.judge.receipts) delegationTables.push(tableOf("Judge · receipts", ["note"], [[D.judge.note]]));
    delegationTables.push(tableOf("Judge · limits", ["note"], [["Not measured: cost, latency and accuracy. The outcome is an association, not proof the judge was right."]]));
    if (D.judge.use) delegationTables.push(tableOf("Judge · Use", ["site / grader", "decisions"], D.judge.use.map(function (x) { return [x.site + " / " + x.grader, x.count]; })));
    if (D.judge.receipts) delegationTables.push(tableOf("Judge · answers", ["measure", "count", "total", "share"], [
      ["Usable answers", D.judge.usable_answers.validated, D.judge.usable_answers.calls, pct(D.judge.usable_answers.share)],
      ["Followed", D.judge.followed.yes, D.judge.followed.validated, pct(D.judge.followed.share)]]));
    if (D.judge.outcome_association.length) delegationTables.push(tableOf("Judge · Outcome association", ["routed by", "runs", "first pass"], D.judge.outcome_association.map(function (x) { return [x.route_by, x.runs, pct(x.first_pass)]; })));
  }
  if (D.reviews) tabs.push(tableOf("reviews", ["pr", "verdicts"], D.reviews.map(function (x) { return [(x.label || repoLabel(x.repo)) + " #" + x.pr, x.verdicts.join(" → ")]; })));
  if (act.length) {
    var wk = [];
    for (var w = 0; w < act.length; w += 7) { var sum = 0; act.slice(w, w + 7).forEach(function (a) { sum += a.count; }); wk.push([act[w].date, sum]); }
    tabs.push(tableOf("activity by week", ["week of", "events"], wk));
  }
  TABS.forEach(function (tab) {
    if (tab.tableRows.length) {
      tab.tables = tab.panel.appendChild(h("details", "", [t("summary", "", "show the data as tables"), h("div", "tables", tab.tableRows)]));
      tab.tables.open = !!tab.tablesOpen;
    }
  });
  selectTab(selected, false);
  if (focusedTab) {
    TABS.forEach(function (tab) { tab.button.tabIndex = tab === focusedTab ? 0 : -1; });
    focusedTab.button.focus();
  }

  updatedEl = t("span", "updated", ""); statusDot = h("span", "status-dot");
  statusDot.setAttribute("role", "img");
  footerInfo = infoButton("");
  footer = h("div", "status", [statusDot, updatedEl, footerInfo]);
  placeFooter();
  updateFreshness();
  }
  var tipAnchor = null, pinnedTip = null, dismissedTip = null;
  tip.setAttribute("role", "tooltip");
  function closeTip() {
    if (tipAnchor && tipAnchor.classList.contains("info-button")) tipAnchor.setAttribute("aria-expanded", "false");
    tip.hidden = true; tipAnchor = null; pinnedTip = null;
  }
  function showTip(el, x, y) {
    if (!el || el === dismissedTip) return;
    if (tipAnchor !== el) closeTip();
    tipAnchor = el; renderTip(tips.get(el)); tip.hidden = false;
    tip.style.pointerEvents = "auto";
    if (el.classList.contains("info-button")) el.setAttribute("aria-expanded", "true");
    var b = el.getBoundingClientRect();
    tip.style.left = Math.max(8, Math.min(x == null ? b.left : x + 12, window.innerWidth - 286)) + "px";
    tip.style.top = Math.max(8, Math.min(y == null ? b.bottom + 6 : y + 14,
      window.innerHeight - tip.getBoundingClientRect().height - 8)) + "px";
  }
  document.addEventListener("pointermove", function (e) {
    if (pinnedTip || (e.target.closest && e.target.closest("#tip"))) return;
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (dismissedTip !== el) dismissedTip = null;
    if (!el) { if (document.activeElement !== tipAnchor) closeTip(); return; }
    showTip(el, e.clientX, e.clientY);
  });
  document.addEventListener("pointerout", function (e) {
    if (e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest("#tip")) return;
    var next = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest("[data-tip]");
    if (tipAnchor !== next && !pinnedTip && document.activeElement !== tipAnchor) closeTip();
    if (dismissedTip !== next) dismissedTip = null;
  });
  document.addEventListener("focusin", function (e) {
    if (!tips.has(e.target)) return;
    dismissedTip = null; showTip(e.target);
  });
  document.addEventListener("focusout", function () { dismissedTip = null; if (!pinnedTip) closeTip(); });
  document.addEventListener("click", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (!el) return;
    if (pinnedTip === el) { dismissedTip = el; closeTip(); }
    else { dismissedTip = null; showTip(el); pinnedTip = el; }
  });
  document.addEventListener("pointerdown", function (e) {
    if (e.target.closest && e.target.closest("#tip")) return;
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el !== tipAnchor) { dismissedTip = tipAnchor; closeTip(); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { dismissedTip = tipAnchor; closeTip(); }
  });
  draw();

  /* Live update: while the tab is visible, load data.js again. A page on disk cannot watch a file, and this needs no server. */
  var POLL_MS = 5000, loading = false;
  function content(d) { return JSON.stringify(d, function (key, v) { return key === "generated" || key === "freshness" ? undefined : v; }); }
  var shown = content(dataNow());
  function apply() {
    var next = dataNow();
    if (!next || next === D) return;
    D = next;
    var c = content(next);
    if (c !== shown) { shown = c; draw(); } else { updateFreshness(); }
  }
  function poll() {
    updateFreshness();
    if (loading || document.visibilityState !== "visible") return;
    loading = true;
    var s = document.createElement("script");
    s.src = "data.js?t=" + Date.now();
    s.onload = s.onerror = function () { s.remove(); loading = false; apply(); };
    document.head.appendChild(s);
  }
  setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", poll);
})();
