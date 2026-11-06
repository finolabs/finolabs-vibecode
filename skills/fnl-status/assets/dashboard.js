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
      spec.items || [], (spec.chips || []).map(function (chip) { return chip.label; })).filter(Boolean).map(function (part) { return String(part).replace(/[.!?]+$/, ""); }).join("; ").replace(/\s+/g, " ") + ".";
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
    if (state === "accepted") {
      var id = "brick-hatch-" + (++brickId), defs = s("defs"), pattern = s("pattern", {
        id: id, width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)"});
      pattern.appendChild(s("rect", {width: 2, height: 4, fill: "var(--warn)"}));
      defs.appendChild(pattern); svg.appendChild(defs); body.setAttribute("fill", "url(#" + id + ")");
    }
    group.appendChild(body); svg.appendChild(group);
    return svg;
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
      lanes.appendChild(ghosts); lanes.appendChild(t("div", "nodata", "No agents running"));
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
    if (quota.length) {
      quota.forEach(function (q) {
        var fraction = Math.max(0, Math.min(1, Number(q.remaining_fraction) || 0));
        var measured = Date.parse(q.measured);
        var stale = q.unverified || !Number.isFinite(measured) || (Date.now() - measured) / 1000 > 28800;
        var meter = h("div", "quota-bricks" + (stale ? " unverified" : "")), lit = fraction > 0 ? Math.max(1, Math.round(fraction * 10)) : 0;
        for (var i = 0; i < 10; i++) meter.appendChild(brick(stale || i >= lit ? "todo" : fraction <= .1 ? "low" : "done", 14, 7,
          "quota-brick" + (!stale && i < lit ? " lit" : "")));
        if (stale) meter.appendChild(t("span", "quota-unknown", "?"));
        meter.setAttribute("role", "img"); meter.setAttribute("tabindex", "0");
        tipOn(meter, {title: q.agent + " quota", sub: stale ? "unverified" : null,
          rows: [["remaining", Math.round(fraction * 100) + "%"], ["measured", q.measured]], bar: {value: fraction, max: 1, marks: [.1]}});
        capacity.appendChild(h("div", "quota-block capacity-block", [t("div", "capacity-caption", q.agent + " quota"), meter]));
      });
      TABS.get("agents").tableRows.push(tableOf("quota", ["family", "remaining", "measured", "state"], quota.map(function (q) {
        return [q.agent, pct(q.remaining_fraction), q.measured, q.unverified ? "unverified" : "verified"];
      })));
    }
    TABS.get("agents").tableRows.push(tableOf("agent state", ["measure", "count"], [
      ["running now", open.length], ["parallel slots", limit], ["past the check time", late], ["not started by coordinator", unowned],
      ["named processes", available ? processes.length : "unavailable"],
      ["app processes", available ? Object.keys(snapshot.apps || {}).reduce(function (sum, family) { return sum + snapshot.apps[family]; }, 0) : "unavailable"]]));
    if (available) TABS.get("agents").tableRows.push(tableOf("process roots", ["family", "elapsed seconds", "descendants", "coordinator match"], processes.map(function (p) {
      return [p.family, p.elapsed_seconds, Object.keys(p.descendants || {}).map(function (name) { return name + ": " + p.descendants[name]; }).join(", ") || "none",
        p.not_started_by_coordinator ? "not started by coordinator" : "family match only"];
    })));
    TABS.get("agents").tableRows.push(tableOf("dispatch budgets", ["agent / model / task", "elapsed / budget", "check", "liveness"], open.map(function (run) {
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
    lines.push(tableOf("project completion", ["done", "total", "completion", "an agent is on it", "to do"],
      [[done, total, completionPercent(done, total) + "%", active, total - done - active]]));
    if (p.reason) line(p.reason);
    (p.features || []).forEach(function (feature) {
      line("feature " + String(feature.feature).padStart(3, "0") + " · " + feature.done + " / " + feature.total);
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
        [task.id, task.story || "—", task.phase == null ? "—" : task.phase, task.state,
          runs.map(function (run) { return run.agent + " / " + run.model; }).join(", ") || "—",
          sessions.map(function (session) { return session.id + " / " + session.host; }).join(", ") || "—",
          runs.map(function (run) { return run.id + " / " + run.elapsed_seconds + " seconds · " + run.outcome; }).join(", ") || "—"].forEach(function (value) {
            var cell = h("td"); cell.textContent = value; row.appendChild(cell);
          });
        table.appendChild(row);
      });
      var wrap = h("div", "project-table"); wrap.appendChild(table); lines.push(wrap);
    });
    var counts = p.sessions || {};
    line("Sessions · running now: " + (p.running_now == null ? "unavailable" : p.running_now) + " (machine-wide process count, not identified sessions) · active in the last 24 hours: " + (counts.active_24h || 0) + " · idle: " + (counts.idle || 0));
    line("Delegated runs · " + Object.keys(p.outcomes || {}).map(function (kind) { return kind + ": " + p.outcomes[kind]; }).join(" · "));
    line("label without a feature: " + (p.labels_without_feature || 0) + " · unlinked runs: " + (p.unlinked_runs || 0));
    line("Sessions without a task");
    (p.sessions_without_task || []).forEach(function (session) { line(session.id + " · " + session.host + " · last activity " + session.last); });
    line("Last reviews · " + Object.keys(p.reviews || {}).map(function (kind) { return kind + ": " + p.reviews[kind]; }).join(" · ") + " · manifest " + (p.version || "unknown"));
    (p.skipped || []).forEach(function (reason) { line(reason); });
    return stack(lines);
  }
  function repoLabel(code) {
    var repos = D.progress && D.progress.repositories || {}, key = String(code).replace(/^repo-/, "");
    var project = Object.prototype.hasOwnProperty.call(repos, key) ? repos[key] : null;
    return project && project.label || "repo " + key.slice(0, 4);
  }
  function storyPriority(story) { return story.priority >= 1 && story.priority <= 9 ? story.priority : 10; }
  function unfinishedFeatures(p) { return (p.features || []).filter(function (f) { return f.total > f.done; }); }
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
      var label = tipOn(t("strong", "active-label", project.label), project.label);
      var row = h("div", "active-project", [h("div", "active-identity", [label,
        h("div", "active-meta", [hosts, t("span", "active-last", at ? "last " + last + " ago" : "last unavailable")])])]);
      row.setAttribute("data-repo", project.repo);
      tipOn(row, project.label + " · " + (at ? String(project.last) : "last unavailable") + (!hasTasks ? " · no task list" : ""));
      var percent = Number(project.percent), percentCell;
      if (hasTasks && !unfinished) {
        percentCell = brick("done", 22, 14, "project-done");
        percentCell.setAttribute("aria-hidden", "false"); percentCell.setAttribute("role", "img");
        percentCell.setAttribute("aria-label", "done");
        percentCell.appendChild(s("path", {d: "M6 10l3 3 7-6", fill: "none", stroke: "var(--bg)", "stroke-width": 2,
          "stroke-linecap": "round", "stroke-linejoin": "round", "class": "done-check"}));
      } else {
        percentCell = t("span", "active-percent", "");
        if (project.percent != null && Number.isFinite(percent))
          percentCell.textContent = Math.max(0, Math.min(99, Math.floor(percent))) + "%";
      }
      row.appendChild(projectDetail(snapshot, motion)); row.appendChild(percentCell);
      list.appendChild(row);
    });
    list.appendChild(taskLegend());
    TABS.get("project").tableRows.push(tableOf("active projects", ["project", "hosts", "sessions · 24h", "last", "done"], rows.map(function (row) {
      var percent = Number(row.percent);
      return [row.label, activityHosts(row.hosts).join(", "), row.sessions, activityTime(row.last) ? String(row.last) : "unavailable",
        row.percent == null || !Number.isFinite(percent) ? "—" : Math.max(0, Math.min(100, Math.floor(percent))) + "%"];
    })));
    return list;
  }
  function taskTip(group, feature, story) {
    if (group.length > 1) {
      return {title: group[0].id + " to " + group[group.length - 1].id,
        rows: [["done", "done"], ["agent on it", "active"], ["not accepted", "accepted"], ["to do", "todo"]].map(function (row) {
          return [row[0], group.filter(function (task) { return taskState(task) === row[1]; }).length];
        })};
    }
    var task = group[0], runs = task.runs || [], sessions = task.sessions || [], state = taskState(task);
    return {title: task.id, sub: (story || "untagged") + " · spec " + String(feature).padStart(3, "0"),
      rows: [["agent / model", runs.map(function (run) { return run.agent + " / " + run.model; }).join(", ") || "—"],
        ["session / host", sessions.map(function (session) { return session.id + " / " + session.host; }).join(", ") || "—"]],
      chips: [{label: {done: "done", active: "agent on it", accepted: "not accepted", todo: "to do"}[state], state: state}]};
  }
  function projectDetail(p, motion) {
    var card = h("div", "project-detail");
    unfinishedFeatures(p).forEach(function (feature) {
      var tasks = feature.tasks || [], stories = (feature.stories || []).slice();
      if (tasks.some(function (task) { return !task.story; })) {
        var untagged = tasks.filter(function (task) { return !task.story; });
        stories.push({story: null, priority: null, total: untagged.length, done: untagged.filter(function (task) { return task.state === "done"; }).length});
      }
      var complete = stories.filter(function (story) { return story.total > 0 && story.done === story.total; }).length;
      var header = h("div", "spec-head", [t("span", "spec-label", "spec " + String(feature.feature).padStart(3, "0")), h("i", "spec-rule")]);
      if (complete) header.appendChild(t("span", "finished-stories", "+" + complete + " done"));
      var featureBody = h("div", "feature", [header]);
      stories.filter(function (story) { return story.total > story.done; }).sort(storyOrder).forEach(function (story) {
        var cells = h("div", "cells"), sorted = tasks.filter(function (task) { return (task.story || null) === (story.story || null); }).sort(taskOrder);
        var per = Math.max(1, Math.ceil(sorted.length / 36));
        for (var i = 0; i < sorted.length; i += per) {
          var group = sorted.slice(i, i + per), states = group.map(taskState);
          var state = states.indexOf("active") !== -1 ? "active" : states.indexOf("accepted") !== -1 ? "accepted" :
            states.every(function (x) { return x === "done"; }) ? "done" : "todo";
          var mark = brick(state, 15, 8, "task-brick");
          mark.setAttribute("data-task", group[0].id); mark.setAttribute("data-state", state); mark.setAttribute("data-count", group.length);
          mark.style.setProperty("--snap-delay", Math.min(500, motion.index++ * 10) + "ms");
          tipOn(mark, taskTip(group, feature.feature, story.story));
          mark.setAttribute("aria-hidden", "false"); mark.setAttribute("role", "img");
          cells.appendChild(mark);
        }
        var row = h("div", "story", [t("span", "story-label", story.story || "untagged"), cells, t("span", "story-count", story.done + "/" + story.total)]);
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
      TABS.get("project").tableRows.push(h("div", "tbl", [t("h3", "", repositories[code].label || activeNames[code]), projectData(repositories[code])]));
    });
    return stack(content);
  }
  function projectLimits() {
    return {title: "How to read this", items: [
      "Named projects show local activity in the last 24 hours.",
      "Each small brick is a task; large groups merge by state.",
      "Done means ticked; not accepted remains unfinished.",
      "Finished stories and features are hidden; tables keep details.",
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
  function glyph(kind) {
    var svg = s("svg", { viewBox: "0 0 18 18", "aria-hidden": "true" });
    if (kind === "APPROVE") svg.appendChild(s("circle", { cx: 9, cy: 9, r: 7, fill: "var(--good)" }));
    else svg.appendChild(s("rect", { x: 3.5, y: 3.5, width: 11, height: 11, rx: 1.5, fill: "var(--warn)", transform: "rotate(45 9 9)" }));
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
    ["agents", { label: "Agents", id: "panel-agents", buttonId: "tab-agents" }],
    ["project", { label: "Project", id: "panel-project", buttonId: "tab-project" }],
    ["delegation", { label: "Delegation", id: "panel-delegation", buttonId: "tab-delegation" }],
    ["reviews", { label: "Reviews", id: "panel-reviews", buttonId: "tab-reviews" }]
  ]);
  var selected = "overview";
  function hashTab() { return window.location.hash.slice(1); }
  function initialTab() {
    if (window.location.hash) return TABS.has(hashTab()) ? hashTab() : "overview";
    try { var value = localStorage.getItem("fnl-tab"); if (TABS.has(value)) return value; } catch (e) { /* storage can be blocked */ }
    return "overview";
  }
  selected = initialTab();
  function selectTab(name, remember) {
    selected = TABS.has(name) ? name : "overview";
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
    var strip = h("div", "tablist"), names = Array.from(TABS.keys());
    strip.setAttribute("role", "tablist"); strip.setAttribute("aria-label", "Dashboard sections");
    TABS.forEach(function (tab, name) {
      var button = t("button", "", tab.label), panel = h("div", "tabpanel");
      button.type = "button";
      button.setAttribute("role", "tab"); button.setAttribute("id", tab.buttonId);
      button.setAttribute("aria-controls", tab.id);
      panel.setAttribute("role", "tabpanel"); panel.setAttribute("id", tab.id);
      panel.setAttribute("aria-labelledby", tab.buttonId); panel.tabIndex = 0; panel.hidden = true;
      var count = null;
      if (name === "agents" && D.running) count = (D.running.open || []).length;
      if (name === "project" && D.progress) count = namedActivity(D.progress).length;
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
      var signature = name === "agents" ? JSON.stringify(D.running) : name === "project" ? JSON.stringify(D.progress) : "";
      if (signature !== tab.signature) tab.pendingAnimation = true;
      tab.signature = signature;
      tab.button = button; tab.panel = panel; tab.tableRows = [];
      strip.appendChild(button);
    });
    app.appendChild(strip);
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

  document.getElementById("wtitle").textContent = "~/finolabs-vibecode — fnl-status";
  var sess = D.sessions || {}, k = D.kpi || {}, sp = k.spark || {};
  app.appendChild(h("div", "cmd", [
    t("span", "ps", "$"), t("span", "", "fnl-status" + (D.period ? " --since " + D.period.days + "d" : "")), h("span", "cursor"),
    t("span", "meta", D.period ? D.period.from + " → " + D.period.to : "")
  ]));
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
  var overview = TABS.get("overview").panel, delegation = TABS.get("delegation").panel;
  TABS.get("agents").panel.appendChild(pane("running now", infoButton(runningLimits() || "not available yet"), "", runningPanel(), "not available yet"));
  TABS.get("project").panel.appendChild(pane("project progress", infoButton(projectLimits()), "", projectPanel(), "not available yet"));

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
  band1.appendChild(pane("router coverage", "sessions", "", rt, missing("router") || "hooks not installed or consent not given", "stack"));

  var rv = null;
  if (D.reviews && D.reviews.length) {
    var rs = D.review_stats || { total: D.reviews.length, reworked: D.reviews.filter(function (x) { return x.verdicts.indexOf("REWORK") > -1; }).length };
    rv = stack([h("div", "stat", [t("strong", "", pct(rs.total ? rs.reworked / rs.total : null)), t("span", "", "of " + rs.total + " pull requests needed rework")]),
      h("div", "rv", D.reviews.map(function (x) {
        var seq = h("div", "seq");
        x.verdicts.slice(0, 8).forEach(function (v, i) { if (i) seq.appendChild(h("span", "ln")); seq.appendChild(tipOn(glyph(v), v)); });
        seq.setAttribute("data-dots", Math.min(8, x.verdicts.length));
        if (x.verdicts.length > 8) seq.appendChild(t("span", "more-rounds", "+" + (x.verdicts.length - 8)));
        tipOn(seq, x.verdicts.length + " rounds · " + x.verdicts.join(" → "));
        return tipOn(h("div", "r", [t("span", "meta review-label", (x.label || repoLabel(x.repo)) + " #" + x.pr), seq]),
          (x.label || repoLabel(x.repo)) + " · PR #" + x.pr + ": " + x.verdicts.join(" → "));
      })), legend([["approve", "var(--good)"], ["rework", "var(--warn)"]])]);
  }
  var reviewPane = pane("review gate", "pull requests", "", rv, missing("reviews") || "no review comments recorded", "rv");

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
  TABS.get("reviews").panel.appendChild(reviewPane);
  overview.appendChild(band2);

  /* Delegation lollipop */
  var dl = null;
  if (D.delegation && D.delegation.length) {
    var ax = h("div", "ax", [t("span", "", "0%"), t("span", "", "60%"), t("span", "", "100%")]);
    ax.children[0].style.left = "0"; ax.children[1].style.left = "60%"; ax.children[2].style.left = "100%";
    var rows = [h("div", "r h", [h("span"), ax, t("span", "", "quota"), t("span", "", "error")])];
    D.delegation.forEach(function (x) {
      var small = x.runs < 5, fp = x.first_pass, trk = h("div", "trk"), th = h("i", "th");
      th.style.left = "60%"; trk.appendChild(th);
      if (fp != null) {
        var col = small ? "var(--faint)" : fp < .6 ? "var(--crit)" : "var(--good)", st = h("i", "stem"), dot = h("i", "dot" + (small ? " open" : ""));
        st.style.width = (fp * 100) + "%"; st.style.background = col;
        dot.style.left = (fp * 100) + "%"; dot.style.color = col;
        tipOn(dot, "first pass " + pct(fp) + (small ? " (fewer than 5 runs, not judged)" : ""));
        trk.appendChild(st); trk.appendChild(dot);
      } else trk.appendChild(t("span", "na", "no judged run"));
      function cnt(n, c) { var e = t("span", "c" + (n ? "" : " z"), n); e.style.setProperty("--c", c); return e; }
      rows.push(tipOn(h("div", "r", [h("div", "who", [t("span", "", x.agent + " · " + x.grade + " · n=" + x.runs), t("span", "meta", x.model)]), trk, cnt(x.quota, "var(--warn-text, var(--warn))"), cnt(x.error, "var(--crit)")]),
        x.agent + " " + x.model + " (" + x.grade + "): " + x.runs + " runs, first pass " + pct(fp) + ", quota " + x.quota + ", error " + x.error + ", median " + x.median_min + " min"));
    });
    dl = stack([h("div", "dl", rows), legend([["first pass at or above 60%", "var(--good)"], ["below 60%", "var(--crit)"], ["open ring: fewer than 5 runs", "var(--faint)"]])]);
  }
  if (D.kept) {
    var plural = function (n, word) { return n + " " + word + (n === 1 ? "" : "s"); };
    var keptLine = t("p", "meta", plural(D.kept.tasks, "task") + " kept by the coordinator in " + plural(D.kept.receipts, "receipt") + (D.kept.handed_off == null ? "" : "; " + plural(D.kept.handed_off, "implementation run") + " handed off"));
    dl = stack([keptLine, dl || t("div", "nodata", "no data: " + (missing("delegation") || "ledger is empty"))]);
  }
  delegation.appendChild(pane("delegation", "from the dispatch ledger", "wide", dl, missing("delegation") || "ledger is empty", "dl"));

  /* Judge receipts and a separate outcome association from the ledger. */
  if (D.judge) {
    var j = D.judge, judgeParts = [];
    if (j.receipts) {
      judgeParts.push(t("h3", "", "Use"));
      judgeParts.push(hbars(j.use.map(function (x) { return { n: x.site + " · " + x.grader, v: x.count }; }), "var(--p)"));
      [["Usable answers", j.usable_answers.share, j.usable_answers.validated, j.usable_answers.calls],
       ["Followed", j.followed.share, j.followed.yes, j.followed.validated]].forEach(function (x) {
        var bar = h("i"), value = pct(x[1]) + " (" + x[2] + "/" + x[3] + ")";
        bar.style.width = ((x[1] || 0) * 100) + "%"; bar.style.background = "var(--p)";
        judgeParts.push(h("div", "hb", [h("div", "r", [t("span", "n", x[0]),
          h("span", "trk", [bar, t("span", "v", x[1] == null ? "no answers" : value)])])]));
      });
    } else judgeParts.push(t("p", "meta", j.note));
    judgeParts.push(t("h3", "", "Outcome association"));
    if (j.outcome_association.length) {
      var jax = h("div", "ax", [t("span", "", "0%"), t("span", "", "60%"), t("span", "", "100%")]);
      jax.children[0].style.left = "0"; jax.children[1].style.left = "60%"; jax.children[2].style.left = "100%";
      var jrows = [h("div", "r h", [h("span"), jax, t("span", "", "first pass"), h("span")])];
      j.outcome_association.forEach(function (x) {
        var small = x.runs < 5, col = small ? "var(--faint)" : x.first_pass < .6 ? "var(--crit)" : "var(--good)";
        var track = h("div", "trk"), line = h("i", "th"), stem = h("i", "stem"), dot = h("i", "dot" + (small ? " open" : ""));
        line.style.left = "60%";
        stem.style.width = (x.first_pass * 100) + "%"; stem.style.background = col;
        dot.style.left = (x.first_pass * 100) + "%"; dot.style.color = col;
        tipOn(dot, "first pass " + pct(x.first_pass) + (small ? " (fewer than 5 runs, not judged)" : ""));
        track.appendChild(line); track.appendChild(stem); track.appendChild(dot);
        jrows.push(h("div", "r", [t("span", "who", x.route_by + " · n=" + x.runs), track, t("span", "", pct(x.first_pass)), h("span")]));
      });
      judgeParts.push(h("div", "dl", jrows));
      judgeParts.push(legend([["first pass at or above 60%", "var(--good)"], ["below 60%", "var(--crit)"], ["open ring: fewer than 5 runs, not judged", "var(--faint)"]]));
    } else judgeParts.push(t("p", "meta", j.outcome_note));
    judgeParts.push(t("p", "meta", "Not measured: cost, latency and accuracy. The outcome is an association, not proof the judge was right."));
    delegation.appendChild(pane("Judge", "receipts and dispatch ledger", "wide", stack(judgeParts)));
  } else delegation.appendChild(pane("Judge", "receipts and dispatch ledger", "wide", null, missing("judge") || "not available yet"));

  /* Tables follow their panes; sources and footer stay shared. */
  var tabs = TABS.get("overview").tableRows, delegationTables = TABS.get("delegation").tableRows;
  if (D.use) tabs.push(tableOf("use", ["name", "calls"], D.use.map(function (u) { return [u.name, u.count]; })));
  if (D.load && D.load.top) tabs.push(tableOf("load (estimate)", ["skill", "tokens", "loads"], D.load.top.map(function (x) { return [x.name, x.tokens, x.loads]; })));
  if (D.depth) tabs.push(tableOf("depth", ["depth", "receipts", "reworked"], D.depth.map(function (x) { return [x.depth, x.receipts, x.reworked]; })));
  if (D.delegation) delegationTables.push(tableOf("delegation", ["agent / model / grade", "runs", "first pass", "quota", "error", "median min", "rework"], D.delegation.map(function (x) { return [x.agent + " / " + x.model + " / " + x.grade, x.runs, pct(x.first_pass), x.quota, x.error, x.median_min, x.rework]; })));
  if (D.kept && D.kept.rows.length) delegationTables.push(tableOf("kept by the coordinator", ["coordinator / reason / settled by", "receipts", "tasks"], D.kept.rows.map(function (x) { return [x.coordinator + " / " + x.reason + " / " + x.route_by, x.receipts, x.tasks]; })));
  if (D.judge) {
    if (D.judge.use) delegationTables.push(tableOf("Judge · Use", ["site / grader", "decisions"], D.judge.use.map(function (x) { return [x.site + " / " + x.grader, x.count]; })));
    if (D.judge.receipts) delegationTables.push(tableOf("Judge · answers", ["measure", "count", "total", "share"], [
      ["Usable answers", D.judge.usable_answers.validated, D.judge.usable_answers.calls, pct(D.judge.usable_answers.share)],
      ["Followed", D.judge.followed.yes, D.judge.followed.validated, pct(D.judge.followed.share)]]));
    if (D.judge.outcome_association.length) delegationTables.push(tableOf("Judge · Outcome association", ["routed by", "runs", "first pass"], D.judge.outcome_association.map(function (x) { return [x.route_by, x.runs, pct(x.first_pass)]; })));
  }
  if (D.reviews) TABS.get("reviews").tableRows.push(tableOf("reviews", ["pr", "verdicts"], D.reviews.map(function (x) { return [(x.label || repoLabel(x.repo)) + " #" + x.pr, x.verdicts.join(" → ")]; })));
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
