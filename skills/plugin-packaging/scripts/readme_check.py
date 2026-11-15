#!/usr/bin/env python3
"""Check a plugin repository's README against references/readme.md (the script items).

Advisory: it reads files only, makes no network call and runs no program. External
links are listed for the agent to open; agent judgment decides what to fix.

Usage: readme_check.py [repository root]
Prints `FAIL <id> <detail>` per finding, `PASS <id>` or `N/A <id>` per item, then
`EXTERNAL <url>` per external link. Exits 0 when nothing failed, 1 when something
failed, 2 when the input cannot be read.
"""

import fnmatch
import ipaddress
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

HOSTS = (("Claude Code", ".claude-plugin"), ("Codex", ".codex-plugin"), ("Antigravity", ".antigravity-plugin"))
# Every host the override's `hosts` may name; Claude Cowork reads the Claude Code manifest format.
KNOWN_HOSTS = dict(HOSTS) | {"Claude Cowork": ".claude-plugin"}
INSTALL_NAMES = {"Claude Cowork": ("claude cowork", "cowork")}  # what an Install heading may call a host
# id, default heading pattern, condition (None: required; "present": checked only when found)
SECTIONS = (
    ("what-you-get", r"What you get", None),
    ("install-at-a-glance", r"Install at a glance", None),
    ("how-it-works", r"How it works", "present"),
    ("start-here", r"Start here\b.*", None),
    ("for-ai-agents", r"For AI agents\b.*", None),
    ("skills", r"Skills", "skills"),
    ("agents", r"Agents", "agents"),
    ("commands", r"Commands", "commands"),
    ("supported-platforms", r"Supported platforms\b.*", None),
    ("install", r"Install", None),
    ("privacy", r"Privacy\b.*", "privacy"),
    ("contributing", r"Contributing\b.*", None),
    ("license", r"Licen[cs]e", None),
    ("acknowledgements", r"Acknowledge?ments", "present"),
)
TABLE_SECTIONS = {"skills", "agents", "commands"}
NON_PLUGIN_SECTIONS = {"what-you-get", "install"}
INSTALL_SECTIONS = ("install-at-a-glance", "for-ai-agents", "install")
ITEMS = ("S1", "S2", "B1", "B2", "B3", "C1", "C2", "H1", "H2", "D1", "L1", "I1", "I2", "K1", "P1")
PLUGIN_ITEMS = {"B2", "B3", "C1", "C2", "H1", "H2", "D1"}
LICENSES = (  # first-line pattern, SPDX id, word the README's License line must carry
    (r"MIT License", "MIT", "MIT"),
    (r"Apache License", "Apache-2.0", "Apache"),
    (r"PolyForm Noncommercial License 1\.0\.0", "PolyForm-Noncommercial-1.0.0", "PolyForm"),
    (r"ISC License", "ISC", "ISC"),
    (r"Mozilla Public License,? Version 2\.0", "MPL-2.0", "Mozilla"),
    (r"BSD 3-Clause", "BSD-3-Clause", "BSD"),
    (r"BSD 2-Clause", "BSD-2-Clause", "BSD"),
    (r"The Unlicense|This is free and unencumbered software", "Unlicense", "Unlicense"),
)
PLACEHOLDERS = re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b|lorem ipsum|coming soon|\{\{[^}]*\}\}|<your-[^>]*>", re.I)
PLACEHOLDER_CASE = re.compile(r"\b(?:todo|tbd|fixme|xxx)\b")  # lower-case words are prose, not markers
COUNT = re.compile(r"\b(\d+) (skill folders|skills?|agents?|commands?)\b")
ROW = re.compile(r"^\|\s*((?:`[^`|]+`[\s,/]*)+)\|")  # one or more backticked names in the first cell
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")  # the closing #s are cut in headings(), without backtracking
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\s*\)")
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\s*\)")
LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")


MAX_READ = 1 << 20  # bytes read from any one repository file
MAX_PATTERN = 200  # characters in one override heading pattern


class BadInput(Exception):
    """Input the script cannot judge: it exits 2 and names the key."""
TAG = re.compile(r"<(img|source|a)\b([^>]*)>", re.I)
ATTR = re.compile(r"([a-zA-Z-]+)\s*=\s*(\"[^\"]*\"|'[^']*')")
SLUG = re.compile(r"github\.com[/:]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def attrs(text):
    return {k.lower(): v[1:-1] for k, v in ATTR.findall(text)}


def blank_comments(text):
    """Blank HTML comments, keeping line numbers (one pass: an opener with no closer ends the scan)."""
    out, pos = [], 0
    while (start := text.find("<!--", pos)) != -1:
        end = text.find("-->", start + 4)
        if end == -1:
            break
        out += [text[pos:start], "\n" * text.count("\n", start, end)]
        pos = end + 3
    out.append(text[pos:])
    return "".join(out)


def opens_comment(line, open_comment):
    """Whether an HTML comment block is still open after this line (inline code already removed).

    Only a `<!--` at the start of a line opens a block, as in CommonMark; one in prose does not.
    A `<!--` after a `-->` on the same line reopens it, as blank_comments reads it."""
    pos = 0
    if not open_comment:
        start = re.match(r" {0,3}<!--", line)
        if not start:
            return False
        pos = start.end()
    while (end := line.find("-->", pos)) != -1:
        reopen = line.find("<!--", end + 3)
        if reopen == -1:
            return False
        pos = reopen + 4
    return True


def strip_code(text):
    """Blank fenced blocks and inline code, keeping line numbers.

    A fence marker inside an open HTML comment opens no fence: the comment is blanked later."""
    out, fence, comment = [], None, False
    for line in text.splitlines():
        mark = re.match(r"^\s*(```+|~~~+)", line)
        if comment:
            out.append(line)
            comment = opens_comment(line, True)
            continue
        if fence:
            out.append("")
            if mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence):
                fence = None
            continue
        if mark:
            fence = mark.group(1)
            out.append("")
            continue
        line = re.sub(r"`[^`]*`", "``", line)
        out.append(line)
        comment = opens_comment(line, False)
    return out


def code_lines(text):
    """Lines inside fenced blocks, plus inline code spans, with their line index."""
    found, fence, comment = [], None, False
    for i, line in enumerate(text.splitlines()):
        mark = re.match(r"^\s*(```+|~~~+)", line)
        if comment:
            comment = opens_comment(line, True)
            continue
        if fence:
            if mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence):
                fence = None
            else:
                found.append((i, line))
            continue
        if mark:
            fence = mark.group(1)
            continue
        found.extend((i, span) for span in re.findall(r"`([^`]+)`", line))
        comment = opens_comment(re.sub(r"`[^`]*`", "``", line), False)
    return found


def plain(heading):
    heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = re.sub(r"<[^>]+>", "", heading)
    return heading.replace("`", "").strip()


def slugify(heading, seen):
    slug = re.sub(r"[^\w\- ]", "", plain(heading).lower()).replace(" ", "-")
    n = seen.get(slug, 0)
    seen[slug] = n + 1
    return slug if n == 0 else f"{slug}-{n}"


def headings(lines):
    """(index, level, text) for Markdown headings outside code (lines already stripped of code)."""
    result = []
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m:
            result.append((i, len(m.group(1)), plain(m.group(2).rstrip().rstrip("#"))))
    return result


def anchors(text):
    body = blank_comments("\n".join(strip_code(text)))  # no id or heading from code or a comment
    seen, found = {}, set()
    for _, _, head in headings(body.split("\n")):
        found.add(slugify(head, seen))
    for tag in re.findall(r"<[a-z][^>]*>", body, re.I):
        a = attrs(tag)
        for key in ("id", "name"):
            if key in a:
                found.add(a[key])
    return found


def read_text(root, path, errors="strict"):
    """A regular file inside root, at most MAX_READ bytes; BadInput for a link out, a non-regular file or an oversize one."""
    real, root = Path(os.path.realpath(path)), Path(os.path.realpath(root))
    if real != root and root not in real.parents:
        raise BadInput(f"{path.name} lies outside the repository")
    fd = os.open(real, os.O_RDONLY | os.O_NONBLOCK)  # a FIFO opens without blocking, then fails the regular-file check
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise BadInput(f"{path.name} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(MAX_READ + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_READ:
        raise BadInput(f"{path.name} is larger than {MAX_READ} bytes")
    return data.decode("utf-8", errors)


def load_json(root, path):
    try:
        return json.loads(read_text(root, path))
    except (OSError, ValueError, RecursionError):
        return None


LOCAL_NAMES = {"localhost", "ip6-localhost", "ip6-loopback", "localhost.localdomain", "localtest.me"}
LOCAL_SUFFIXES = (".localhost", ".local", ".localdomain", ".internal", ".home.arpa", ".lan",
                  ".nip.io", ".sslip.io", ".localtest.me")
NAT64 = ipaddress.ip_network("64:ff9b::/96")


def public_url(url):
    """Whether an http(s) URL names a public host: not loopback, private, link-local, a numeric shorthand, a
    single-label or local-only name, or a well-known name that resolves to loopback. Offline, so names that only DNS
    would reveal as private still pass; deny on doubt."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https") or not host or host in LOCAL_NAMES or host.endswith(LOCAL_SUFFIXES):
        return False
    try:
        ip = ipaddress.ip_address(host.partition("%")[0])  # a zone index (fe80::1%eth0) names a local interface
    except ValueError:
        if ":" in host or "%" in host or "." not in host:
            return False  # an IPv6 form ipaddress refuses, or a single-label name (metadata, router, intranet)
        return not re.fullmatch(r"(?:0x[0-9a-f]*|\d+)(?:\.(?:0x[0-9a-f]*|\d+)){0,3}", host)  # 2130706433, 0x7f.1
    if "%" in host:
        return False
    if ip.version == 6 and ip in NAT64:
        ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)  # NAT64 embeds an IPv4 address in its last 32 bits
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_global and not ip.is_multicast


def repo_slug(value):
    if isinstance(value, dict):
        value = value.get("url", "")
    m = SLUG.search(str(value or "").strip())
    return m.group(1) if m else None


class Check:
    def __init__(self, root):
        self.root = root
        self.text = read_text(root, root / "README.md")
        self.raw = self.text.splitlines()
        # Strip code first, so a comment marker inside a code span or block hides nothing.
        self.lines = blank_comments("\n".join(strip_code(self.text))).split("\n")
        self.heads = headings(self.lines)
        self.failures = {item: [] for item in ITEMS}
        self.na = set()
        self.external = []
        self.config = self.read_config(root, root / ".github" / "readme-standard.json")
        self.manifests, self.missing_hosts = {}, []
        hosts = self.config.get("hosts") or [h for h, _ in HOSTS]
        for host in hosts:
            data = load_json(root, root / KNOWN_HOSTS[host] / "plugin.json")
            if isinstance(data, dict):
                self.manifests[host] = data
            elif "hosts" in self.config:
                self.missing_hosts.append(host)
        # A manifest that ships but the override leaves out would escape every manifest check.
        listed = {KNOWN_HOSTS[h] for h in hosts}
        self.unlisted_hosts = [h for h, folder in HOSTS if folder not in listed and (root / folder / "plugin.json").exists()]
        first = self.manifests.get("Claude Code") or next(iter(self.manifests.values()), {})
        self.name = first.get("name", "")
        interface = first.get("interface") if isinstance(first.get("interface"), dict) else {}
        self.display = first.get("displayName") or interface.get("displayName", "")
        self.name = self.name if isinstance(self.name, str) else ""
        self.display = self.display if isinstance(self.display, str) else ""
        self.repository = first.get("repository", "")
        if isinstance(self.repository, dict):
            self.repository = self.repository.get("url", "")
        self.slug = repo_slug(self.repository)
        first_section = next((i for i, level, _ in self.heads if level == 2), len(self.raw))
        self.header = "\n".join(self.raw[:first_section])

    @staticmethod
    def read_config(root, path):
        if not path.exists():
            return {}
        config = load_json(root, path)
        if not isinstance(config, dict):
            raise BadInput("readme-standard.json is not a JSON object")
        kinds = {"sections": dict, "exclude_skills": list, "catalog": dict, "badge_color": str, "banner_follow_up": str,
                 "hosts": list}
        for key, kind in kinds.items():
            if key in config and not isinstance(config[key], kind):
                raise BadInput(f"readme-standard.json: {key} must be a {kind.__name__}")
        known = {sid for sid, _, _ in SECTIONS}
        for sid, pattern in config.get("sections", {}).items():
            if sid not in known or not isinstance(pattern, str):
                raise BadInput(f"readme-standard.json: sections.{sid} is not a known section with a string pattern")
            if len(pattern) > MAX_PATTERN:
                raise BadInput(f"readme-standard.json: sections.{sid} is longer than {MAX_PATTERN} characters")
            try:
                re.compile(pattern)
            except re.error:
                raise BadInput(f"readme-standard.json: sections.{sid} is not a valid regular expression") from None
        hosts = config.get("hosts", [])
        if "hosts" in config and (not hosts or not all(isinstance(h, str) and h in KNOWN_HOSTS for h in hosts)
                                  or len(set(hosts)) != len(hosts)):
            raise BadInput("readme-standard.json: hosts must list one or more of " + ", ".join(KNOWN_HOSTS))
        if not all(isinstance(p, str) for p in config.get("exclude_skills", [])):
            raise BadInput("readme-standard.json: exclude_skills must list strings")
        if not all(isinstance(v, str) for v in config.get("catalog", {}).values()):
            raise BadInput("readme-standard.json: catalog values must be strings")
        return config

    def fail(self, item, detail):
        self.failures[item].append(detail)

    # Sections ------------------------------------------------------------
    def section_spans(self):
        patterns = dict((sid, pat) for sid, pat, _ in SECTIONS)
        patterns.update(self.config.get("sections", {}))
        found = {}
        for sid, _, _ in SECTIONS:
            levels = (2, 3) if sid in TABLE_SECTIONS else (2,)
            for n, (i, level, head) in enumerate(self.heads):
                if level in levels and re.fullmatch(patterns[sid], head, re.I):
                    end = next((j for j, lv, _ in self.heads[n + 1:] if lv <= level), len(self.lines))
                    found[sid] = (i, end)
                    break
        starts = sorted(start for start, _ in found.values())
        for sid, (start, end) in found.items():
            following = [s for s in starts if s > start]
            found[sid] = (start, min([end] + following))
        return found

    def shipped(self):
        excluded = self.config.get("exclude_skills", [])
        skills = sorted(p.parent.name for p in self.root.glob("skills/*/SKILL.md")
                        if not any(fnmatch.fnmatch(p.parent.name, pat) for pat in excluded))
        agents = []
        for path in sorted(self.root.glob("agents/*.md")):
            m = re.search(r"^name:\s*['\"]?([^'\"\n]+)", read_text(self.root, path), re.M)
            agents.append(m.group(1).strip() if m else path.stem)
        commands = sorted(p.stem for p in self.root.glob("commands/*.md"))
        return {"skills": skills, "agents": agents, "commands": commands}

    def check_sections(self, spans, shipped):
        conditions = {"skills": bool(shipped["skills"]), "agents": bool(shipped["agents"]),
                      "commands": bool(shipped["commands"]), "privacy": (self.root / "PRIVACY.md").is_file()}
        order = []
        for sid, _, cond in SECTIONS:
            needed = cond is None or (cond != "present" and conditions.get(cond))
            if not self.manifests:  # a repository that is not a plugin needs only these
                needed = sid in NON_PLUGIN_SECTIONS
            if sid in spans:
                order.append((spans[sid][0], sid))
            elif needed:
                self.fail("S1", f"missing section: {sid}")
        ranked = [sid for sid, _, _ in SECTIONS]
        for (_, a), (_, b) in zip(sorted(order), sorted(order)[1:]):
            if ranked.index(a) > ranked.index(b):
                self.fail("S1", f"out of order: {a} comes before {b}")
        title = re.search(r"<h1[^>]*>(.*?)</h1>", self.header, re.I | re.S)
        title = plain(title.group(1)) if title else next((h for _, lv, h in self.heads if lv == 1), "")
        if not title:  # a wordmark image stands in for the title
            alts = [m[0] for m in MD_IMAGE.findall(self.header)]
            alts += [attrs(t).get("alt", "") for t in re.findall(r"<img\b[^>]*>", self.header, re.I)]
            title = next((alt for alt in alts if alt.strip()), "")
        names = [n for n in (self.name, self.display) if n]
        if not title:
            self.fail("S2", "no title before the first section")
        elif names and not any(n.lower() in title.lower() for n in names):
            self.fail("S2", f"title {title!r} names neither {' nor '.join(map(repr, names))}")

    # Badges --------------------------------------------------------------
    def check_badges(self, readme_anchors):
        badges = []
        for m in re.finditer(r"<a\b([^>]*)>\s*<img\b([^>]*)>\s*</a>", self.header, re.I | re.S):
            badges.append((attrs(m.group(1)).get("href", ""), attrs(m.group(2))))
        for m in re.finditer(r"\[!\[([^\]]*)\]\(([^)\s]+)\)\]\(([^)\s]+)\)", self.header):
            badges.append((m.group(3), {"alt": m.group(1), "src": m.group(2)}))
        badges = [(href, img) for href, img in badges
                  if "shields.io" in img.get("src", "") or "/badge.svg" in img.get("src", "")]
        hosts_badged, color = set(), self.config.get("badge_color")
        for href, img in badges:
            src = img.get("src", "")
            if not img.get("alt", "").strip():
                self.fail("B1", f"badge without alt text: {src}")
            if href.startswith("#") and href[1:] not in readme_anchors:
                self.fail("B1", f"badge link to missing anchor: {href}")
            elif href and not re.match(r"[a-z]+:", href) and not (self.root / unquote(href.split("#")[0])).exists():
                self.fail("B1", f"badge link to missing file: {href}")
            gh = re.search(r"shields\.io/github/(?:v/)?[a-z-]+/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", src)
            wf = re.search(r"github\.com/([^/]+/[^/]+)/actions/workflows/([^/]+)/badge\.svg", src)
            for slug in filter(None, (gh and gh.group(1), wf and wf.group(1))):
                if self.slug and slug.lower() != self.slug.lower():
                    self.fail("B2", f"badge names {slug}, the manifests name {self.slug}")
            if wf and not (self.root / ".github" / "workflows" / wf.group(2)).is_file():
                self.fail("B2", f"workflow badge names a missing workflow: {wf.group(2)}")
            label = re.search(r"shields\.io/badge/([^?]+)", src)
            if label:
                parts = unquote(label.group(1)).split("-")
                host = next((h for h in KNOWN_HOSTS if parts[0].replace("_", " ") == h), None)
                if host:
                    hosts_badged.add(host)
                    if color and parts[-1].lower() != str(color).lower():
                        self.fail("B3", f"{host} badge colour {parts[-1]}, house style {color}")
        for host in self.manifests:
            if host not in hosts_badged:
                self.fail("B3", f"no badge for {host}, which has a manifest")
        for host in sorted(hosts_badged - set(self.manifests)):
            if (self.root / KNOWN_HOSTS[host] / "plugin.json").is_file():
                self.fail("B3", f"badge for {host}: add it to the override's hosts to serve it")
            else:
                self.fail("B3", f"badge for {host}, which has no manifest")

    # Counts and tables ---------------------------------------------------
    def check_counts(self, spans, shipped):
        kinds = {"skill": "skills", "skills": "skills", "skill folders": "skills",
                 "agent": "agents", "agents": "agents", "command": "commands", "commands": "commands"}
        sources = [("README", "\n".join(self.lines))]
        sources += [(f"{h} manifest", str(m.get("description", ""))) for h, m in self.manifests.items()]
        for where, text in sources:
            for number, word in COUNT.findall(text):
                kind = kinds[word]
                if int(number) != len(shipped[kind]):
                    self.fail("C1", f"{where} says {number} {word}; {len(shipped[kind])} ship")
        # A row is read from the raw line (code spans hold its names) only where it is outside code and comments.
        rows = {name for line, kept in zip(self.raw, self.lines) if kept.startswith("|") and (m := ROW.match(line))
                for name in self.row_names(m.group(1))}
        for kind, names in shipped.items():
            for name in names:
                if name not in rows:
                    self.fail("C2", f"{kind[:-1]} {name} has no table row")
            if kind in spans:
                start, end = spans[kind]
                for line, kept in zip(self.raw[start:end], self.lines[start:end]):
                    m = ROW.match(line) if kept.startswith("|") else None
                    for name in self.row_names(m.group(1)) if m else ():
                        if name not in names:
                            self.fail("C2", f"{kind} table lists {name}, which does not ship")

    def row_names(self, cell):
        """`/plugin:name`, `$name` and `name` all name the same skill or command."""
        prefix = f"{self.name}:"
        names = []
        for name in re.findall(r"`([^`]+)`", cell):
            name = name.strip().lstrip("/$")
            names.append(name[len(prefix):] if self.name and name.startswith(prefix) else name)
        return names

    # Hosts and install ---------------------------------------------------
    def check_hosts(self, spans):
        header_text = re.sub(r"<[^>]+>", " ", self.header)
        install = spans.get("install")
        subheads = [h.lower() for i, lv, h in self.heads if install and install[0] <= i < install[1]]
        for host in self.manifests:
            if host.lower() not in header_text.lower():
                self.fail("H1", f"header does not name {host}")
            if not any(n in h for h in subheads for n in INSTALL_NAMES.get(host, (host.lower(),))):
                self.fail("H1", f"Install has no subsection for {host}")
        own = {self.name.lower()} if self.name else set()
        markets = set()
        for path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            data = load_json(self.root, self.root / path)
            if isinstance(data, dict) and data.get("name"):
                markets.add(str(data["name"]).lower())
        catalog = self.config.get("catalog") if isinstance(self.config.get("catalog"), dict) else {}
        if catalog.get("marketplace"):
            markets.add(str(catalog["marketplace"]).lower())
        sources = {s.lower() for s in (self.slug, catalog.get("repository")) if s}
        ranges = [spans[s] for s in INSTALL_SECTIONS if s in spans]
        for i, line in code_lines(self.text):
            if not any(a <= i < b for a, b in ranges):
                continue
            for verb, value in re.findall(r"\b(plugin install|plugin add|marketplace add|skills add)\s+(\S+)", line):
                value = value.strip("'\"").rstrip("/")
                if verb == "marketplace add" or verb == "skills add" or value.startswith("http"):
                    slug = repo_slug(value) or value.lower()
                    if slug.lower() not in sources:
                        self.fail("H2", f"line {i + 1}: {verb} {value} is neither this repository nor the catalog")
                    continue
                plugin, _, market = value.partition("@")
                if own and plugin.lower() not in own:
                    self.fail("H2", f"line {i + 1}: {verb} {value} does not name {self.name}")
                if market and market.lower() not in markets:
                    self.fail("H2", f"line {i + 1}: marketplace {market} is not this repository's or the catalog's")

    # Description and license ---------------------------------------------
    def check_descriptions(self):
        descriptions = {h: m.get("description", "") for h, m in self.manifests.items()}
        for host in [h for h, d in descriptions.items() if not isinstance(d, str)]:
            self.fail("D1", f"{host} manifest description is not a string")
            descriptions[host] = repr(descriptions[host])  # hashable, and differs from every string description
        if len(set(descriptions.values())) > 1:
            self.fail("D1", "manifest descriptions differ: " + ", ".join(sorted(descriptions)))
        data = load_json(self.root, self.root / ".claude-plugin" / "marketplace.json")
        main = next(iter(descriptions.values()), None)
        for entry in (data or {}).get("plugins", []) if isinstance(data, dict) else []:
            if isinstance(entry, dict) and entry.get("name") == self.name and "description" in entry:
                if entry["description"] != main:
                    self.fail("D1", ".claude-plugin/marketplace.json entry description differs from the manifest")

    def check_license(self, spans):
        path = next((self.root / n for n in LICENSE_FILES if (self.root / n).exists()), None)  # read_text refuses a non-regular one
        if path is None:
            self.fail("L1", "no LICENSE, LICENSE.md, LICENSE.txt or COPYING file")
            return
        head = read_text(self.root, path, errors="replace")[:400]
        match = next(((spdx, word) for pat, spdx, word in LICENSES if re.search(pat, head, re.I)), None)
        if not match:
            self.fail("L1", "LICENSE not recognized; check the License line by hand")
            return
        spdx, word = match
        for host, manifest in self.manifests.items():
            if manifest.get("license") != spdx:
                self.fail("L1", f"{host} manifest license {manifest.get('license')!r}, LICENSE is {spdx}")
        if "license" in spans:
            start, end = spans["license"]
            body = "\n".join(self.lines[start + 1:end])
            if word.lower() not in body.lower():
                self.fail("L1", f"License section does not name {spdx}")
            if path.name not in body:
                self.fail("L1", f"License section does not link {path.name}")

    # Images and links ----------------------------------------------------
    def local(self, target):
        return target and not re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) and not target.startswith("#")

    def check_images_links(self, readme_anchors):
        body = "\n".join(self.lines)
        for m in TAG.finditer(body):
            kind, a = m.group(1).lower(), attrs(m.group(2))
            if kind == "img":
                if not a.get("alt", "").strip():
                    self.fail("I1", f"image without alt text: {a.get('src', '')}")
                self.target(a.get("src", ""), "I1", readme_anchors)
            elif kind == "source":
                for src in a.get("srcset", "").split(","):
                    self.target(src.strip().split(" ")[0], "I1", readme_anchors)
            elif "href" in a:
                self.target(a["href"], "K1", readme_anchors)
        for alt, bracketed, bare in MD_IMAGE.findall(body):
            src = bracketed or bare
            if not alt.strip():
                self.fail("I1", f"image without alt text: {src}")
            self.target(src, "I1", readme_anchors)
        for bracketed, bare in LINK.findall(body):
            self.target(bracketed or bare, "K1", readme_anchors)
        for block in re.findall(r"<picture\b.*?</picture>", body, re.I | re.S):
            media = [(re.sub(r"\s", "", attrs(t).get("media", "")), attrs(t).get("srcset", ""))
                     for t in re.findall(r"<source\b[^>]*>", block, re.I)]
            if not any("prefers-color-scheme" in m for m, _ in media):
                continue  # a responsive <picture>, not a light/dark pair
            dark = [src for m, src in media if "prefers-color-scheme:dark" in m]
            img = [attrs(t).get("src", "") for t in re.findall(r"<img\b[^>]*>", block, re.I)]
            if not dark or not img:
                self.fail("I2", "a <picture> lacks a dark <source> or a light <img>")
            elif dark[0].split(" ")[0] == img[0]:
                self.fail("I2", f"a <picture> uses the same file for light and dark: {img[0]}")

    def target(self, target, item, readme_anchors):
        if not target:
            return
        if re.match(r"https?://|file:", target, re.I):
            if not public_url(target):
                self.fail(item, f"link to a local or private address: {target}")
            elif target not in self.external:
                self.external.append(target)
            return
        if target.startswith("#"):
            if unquote(target[1:]) not in readme_anchors:
                self.fail(item, f"missing anchor: {target}")
            return
        if not self.local(target):
            return
        path, _, anchor = target.partition("#")
        file = (self.root / unquote(path.split("?")[0]).lstrip("/")).resolve()
        if file != self.root and self.root not in file.parents:
            self.fail(item, f"outside the repository: {path}")
        elif not file.exists():
            self.fail(item, f"missing file: {path}")
        elif anchor and file.suffix == ".md":
            try:
                found = anchors(read_text(self.root, file))
            except (OSError, UnicodeDecodeError, BadInput):
                self.fail(item, f"cannot read the anchors of {path}")
                return
            if unquote(anchor) not in found:
                self.fail(item, f"missing anchor: {target}")

    def check_placeholders(self):
        for i, line in enumerate(self.lines):
            for m in PLACEHOLDERS.finditer(line):
                if not PLACEHOLDER_CASE.fullmatch(m.group(0)):
                    self.fail("P1", f"line {i + 1}: {m.group(0)}")

    def run(self):
        spans, shipped = self.section_spans(), self.shipped()
        readme_anchors = anchors(self.text)
        self.check_sections(spans, shipped)
        self.check_images_links(readme_anchors)
        self.check_placeholders()
        self.check_license(spans)
        for host in self.missing_hosts:  # reported even when no listed host has a manifest
            self.fail("H1", f"the hosts override lists {host}, which has no manifest")
        for host in self.unlisted_hosts:
            self.fail("H1", f"{KNOWN_HOSTS[host]}/plugin.json ships, but the hosts override leaves out {host}")
        if self.manifests:
            self.check_badges(readme_anchors)
            self.check_counts(spans, shipped)
            self.check_hosts(spans)
            self.check_descriptions()
        else:
            self.na |= PLUGIN_ITEMS - {item for item in PLUGIN_ITEMS if self.failures[item]}
        failed = False
        for item in ITEMS:
            for detail in self.failures[item]:
                failed = True
                print(f"FAIL {item} {detail}")
        for item in ITEMS:
            if item in self.na:
                print(f"N/A {item} no plugin manifest")
            elif not self.failures[item]:
                print(f"PASS {item}")
        for url in self.external:
            print(f"EXTERNAL {url}")
        return 1 if failed else 0


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not (root / "README.md").is_file():
        print(f"no README.md in {root.name or root}", file=sys.stderr)
        return 2
    try:
        return Check(root).run()
    except BadInput as error:
        print(f"bad input: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read the repository: {error.__class__.__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
