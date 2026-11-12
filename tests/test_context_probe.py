"""Context probe acceptance: fake programs, a synthetic account and a temporary data root only."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

from tests.test_context_snapshot import ctx
from tests.test_handover_state import setup_store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quota_probe as qp
import data_root as dr

SESSION = "00000000-0000-4000-8000-0000000000a1"
CLAUDE_ARGV = ["-p", "/context", "--resume", SESSION, "--fork-session", "--no-session-persistence",
               "--output-format", "json"]
INITIALIZE = {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "fnl-context", "version": "1"}}}


def claude_result(text="Context Usage\nclaude-model\nTokens: 412.1k / 1m (41%)\n", **changes):
    value = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 0,
             "total_cost_usd": 0, "result": text, "session_id": "11111111-1111-4111-8111-111111111111"}
    value.update(changes)
    return json.dumps(value)


def codex_body(log, status=None, goal=None, extra=""):
    """A synthetic app-server that asserts each client message and records what it received."""
    status = {"type": "idle"} if status is None else status
    usage = {"total": {"totalTokens": 999999}, "last": {"totalTokens": 36528}, "modelContextWindow": 475000}
    return (
        "import sys,json,time\n"
        f"log=open({str(log)!r},'a')\n"
        "def get():\n"
        "    line=sys.stdin.readline()\n"
        "    log.write(line); log.flush()\n"
        "    return json.loads(line)\n"
        "def put(m): print(json.dumps(m),flush=True)\n"
        f"assert get()=={INITIALIZE!r}\n"
        "put({'id':7,'method':'item/tool/requestUserInput','params':{}})\n"
        "put({'id':1,'result':{'userAgent':'synthetic'}})\n"
        "assert get()=={'method':'initialized','params':{}}\n"
        f"assert get()=={{'id':2,'method':'thread/read','params':{{'threadId':{SESSION!r}}}}}\n"
        f"assert get()=={{'id':3,'method':'thread/goal/get','params':{{'threadId':{SESSION!r}}}}}\n"
        f"put({{'id':2,'result':{{'thread':{{'id':{SESSION!r},'status':{status!r}}}}}}})\n"
        f"put({{'id':3,'result':{{'goal':{goal!r}}}}})\n"
        f"assert get()=={{'id':4,'method':'thread/resume','params':{{'threadId':{SESSION!r}}}}}\n"
        f"put({{'method':'thread/tokenUsage/updated','params':{{'threadId':'other','tokenUsage':{{'last':{{'totalTokens':5}},'modelContextWindow':10}}}}}})\n"
        "put({'id':8,'method':'account/chatgptAuthTokens/refresh','params':{}})\n"
        "put({'id':4,'result':{}})\n"
        + extra +
        f"put({{'method':'thread/tokenUsage/updated','params':{{'threadId':{SESSION!r},'turnId':'t','tokenUsage':{usage!r}}}}})\n"
        "time.sleep(60)\n")


class ContextProbeTest(unittest.TestCase):
    def setUp(self):
        self.root = setup_store(self)
        self.home = dr.account_home()
        self.base = self.home.parent
        patch = mock.patch.dict(os.environ, {}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.bin = self.base / "bin"
        self.bin.mkdir(mode=0o700)
        self.config_dir = self.home / ".claude"
        self.config_dir.mkdir(mode=0o700)
        self.seen = self.base / "seen"
        self.interpreter = str(Path(sys.executable).resolve())
        # Same seams as the quota probe tests: trust only this running interpreter
        # and the system temporary folder; every other check stays in force.
        checked_path = qp.checked_path
        def test_path(value, **kwargs):
            if str(value) == self.interpreter and not kwargs.get("directory"):
                return b""
            return checked_path(value, **kwargs)
        excluded = qp.excluded
        def test_excluded(path):
            if "downloads" in (part.lower() for part in Path(path).parts):
                return excluded(path)
        for name, value in (("checked_path", test_path), ("excluded", test_excluded)):
            patch = mock.patch.object(qp, name, side_effect=value)
            patch.start()
            self.addCleanup(patch.stop)

    def fake(self, agent, body):
        path = self.bin / agent
        path.write_text("#!" + self.interpreter + "\n" + body)
        path.chmod(0o700)
        return {"executable": str(path), "resolved": str(path), "interpreter": self.interpreter}

    def configure(self, entries, folders=None, confirmed=True, quota="on"):
        folders = folders or {"default": str(self.config_dir)}
        lines = ["## Quota probe", "", "- Quota probe: " + quota, "- Date: 2026-11-05", "- Agents: " + ", ".join(entries)]
        for agent, entry in entries.items():
            lines += [f"- Executable {agent}: {entry['executable']}", f"- Interpreter {agent}: {entry['interpreter']}",
                      f"- Resolved {agent}: {entry['resolved']}"]
            if confirmed:
                lines.append(f"- Resolved digest {agent}: {hashlib.sha256(entry['resolved'].encode()).hexdigest()}")
            if agent == "claude":
                lines += [f"- Claude config: {label}: {path}" for label, path in folders.items()]
        dr.write_data("host.md", ("\n".join(lines) + "\n").encode())

    def claude(self, output=None, exit_code=0):
        output = claude_result() if output is None else output
        body = ("import sys,os,json\n"
                f"open({str(self.seen)!r},'w').write(json.dumps({{'argv':sys.argv[1:],'cwd':os.getcwd(),"
                "'files':os.listdir('.')}))\n"
                f"print({output!r})\n"
                f"sys.exit({exit_code})\n")
        return self.fake("claude", body)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        original_write = os.write
        def output(fd, data):
            if fd == 1:
                out.write(data.decode("utf-8"))
                return len(data)
            return original_write(fd, data)
        with mock.patch.object(os, "write", side_effect=output), \
                mock.patch.object(sys, "argv", ["context_snapshot.py", *args]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ctx.main()
        return code, out.getvalue(), err.getvalue()

    def refused(self, *args):
        self.assertEqual(self.cli(*args), (3, "", ctx.NO_PROBE + "\n"))

    def snapshot(self, host):
        return json.loads((self.root / "state/context" / ctx.filename(SESSION, host)).read_bytes())

    def test_claude_runs_the_fixed_argv_in_a_neutral_folder_and_stores_counts_only(self):
        self.configure({"claude": self.claude()})
        code, out, err = self.cli("probe", "--host", "claude", "--session", SESSION)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), {"used": 412100, "window": 1000000, "percent": 41,
                                           "age_seconds": 0, "stale": False})
        seen = json.loads(self.seen.read_text())
        self.assertEqual(seen["argv"], CLAUDE_ARGV)
        self.assertEqual(seen["files"], [])
        self.assertNotEqual(Path(seen["cwd"]).resolve(), Path.cwd().resolve())
        self.assertEqual(Path(seen["cwd"]).parent, self.root / "tmp")
        self.assertFalse(Path(seen["cwd"]).exists())
        data = self.snapshot("claude")
        self.assertEqual(set(data), ctx.FIELDS)
        self.assertEqual((data["used"], data["window"], data["percent"], data["version"], data["host"]),
                         (412100, 1000000, 41, "unknown", "claude"))
        self.assertEqual(json.loads(self.cli("read", "--session", SESSION)[1])["used"], 412100)
        raw = (self.root / "state/context" / ctx.filename(SESSION, "claude")).read_text()
        self.assertNotIn(SESSION, raw)

    def test_changed_program_path_is_named_and_never_run(self):
        entry = self.claude()
        versions = self.bin / "versions"
        versions.mkdir(mode=0o700)
        current = versions / "2.1.319"
        Path(entry["executable"]).rename(current)
        Path(entry["executable"]).symlink_to(current)
        self.configure({"claude": dict(entry, resolved=str(versions / "2.1.318"))})
        code, out, err = self.cli("probe", "--host", "claude", "--session", SESSION)
        self.assertEqual((code, out), (3, ""))
        self.assertEqual(err, "Context probe claude: program changed since setup (2.1.318 to 2.1.319); "
                              "run /setup add quota to re-confirm the new path\n")
        self.assertNotIn(str(self.base), err)
        self.assertFalse(self.seen.exists())
        self.assertFalse((self.root / "state/context" / ctx.filename(SESSION, "claude")).exists())
        self.configure({"claude": dict(entry, resolved=str(current))})
        self.assertEqual(self.cli("probe", "--host", "claude", "--session", SESSION)[0], 0)
        self.assertTrue(self.seen.exists())

    def test_claude_window_units_and_integer_counts(self):
        for text, used, window in (("Tokens: 31k / 200k (15%)", 31000, 200000),
                                   ("Tokens: 950 / 200k (0%)", 950, 200000),
                                   ("**Tokens:** ignored\nTokens: 1.5m / 2m (75%)", 1500000, 2000000)):
            with self.subTest(text=text):
                self.configure({"claude": self.claude(claude_result(text))})
                code, out, _ = self.cli("probe", "--host", "claude", "--session", SESSION)
                self.assertEqual(code, 0)
                self.assertEqual((json.loads(out)["used"], json.loads(out)["window"]), (used, window))

    def test_claude_refuses_a_model_turn_cost_error_or_ambiguous_reply(self):
        for output, exit_code in ((claude_result(num_turns=1), 0), (claude_result(total_cost_usd=0.01), 0),
                                  (claude_result(is_error=True), 0), (claude_result(subtype="error"), 0),
                                  (claude_result(num_turns=None), 0), (claude_result("no counts"), 0),
                                  (claude_result("Tokens: 1k / 2k (50%)\nTokens: 1k / 2k (50%)"), 0),
                                  (claude_result("Tokens: 1k / 0 (0%)"), 0), (claude_result(), 1),
                                  ("not json", 0), ('{"result": "Tokens: 1k / 2k", "result": "x"}', 0)):
            with self.subTest(output=output[:60], exit_code=exit_code):
                self.configure({"claude": self.claude(output, exit_code)})
                self.refused("probe", "--host", "claude", "--session", SESSION)
                self.assertFalse((self.root / "state/context" / ctx.filename(SESSION, "claude")).exists())

    def test_claude_config_folder_is_chosen_from_the_confirmed_list(self):
        work = self.home / "work-config"
        work.mkdir(mode=0o700)
        self.configure({"claude": self.claude()}, {"default": str(self.config_dir), "work": str(work)})
        self.refused("probe", "--host", "claude", "--session", SESSION)
        self.assertFalse(self.seen.exists())
        self.refused("probe", "--host", "claude", "--session", SESSION, "--config", "other")
        self.assertFalse(self.seen.exists())
        self.assertEqual(self.cli("probe", "--host", "claude", "--session", SESSION, "--config", "work")[0], 0)
        self.assertTrue(self.seen.exists())
        self.refused("probe", "--host", "codex", "--session", SESSION, "--config", "work")

    def test_codex_sends_fixed_payloads_ignores_requests_and_reads_the_first_matching_update(self):
        log = self.base / "codex.log"
        self.configure({"codex": self.fake("codex", codex_body(log))})
        started = time.monotonic()
        code, out, err = self.cli("probe", "--host", "codex", "--session", SESSION)
        self.assertEqual((code, err), (0, ""))
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(json.loads(out), {"used": 36528, "window": 475000, "percent": 7,
                                           "age_seconds": 0, "stale": False})
        methods = [json.loads(line).get("method") for line in log.read_text().splitlines()]
        self.assertEqual(methods, ["initialize", "initialized", "thread/read", "thread/goal/get", "thread/resume"])
        data = self.snapshot("codex")
        self.assertEqual((data["host"], data["used"], data["window"], data["version"]),
                         ("codex", 36528, 475000, "unknown"))
        self.assertEqual(ctx.filename(SESSION, "codex"),
                         hashlib.sha256(("codex:" + SESSION).encode()).hexdigest()[:16] + ".json")
        self.assertEqual(json.loads(self.cli("read", "--session", SESSION, "--host", "codex")[1])["used"], 36528)
        self.assertEqual(json.loads(self.cli("read", "--latest", "--host", "codex")[1])["window"], 475000)
        self.assertEqual(self.cli("read", "--session", SESSION)[0], 3)

    def test_codex_not_loaded_thread_is_read(self):
        log = self.base / "codex.log"
        self.configure({"codex": self.fake("codex", codex_body(log, status={"type": "notLoaded"}))})
        self.assertEqual(self.cli("probe", "--host", "codex", "--session", SESSION)[0], 0)

    def test_codex_stops_before_resume_unless_idle_or_not_loaded_without_goal(self):
        cases = [({"type": "active", "activeFlags": []}, None), ({"type": "systemError"}, None),
                 ({"type": "idle"}, {"objective": "synthetic"}), ({"type": "idle"}, False),
                 ("idle", None), (None, None)]
        for status, goal in cases:
            with self.subTest(status=status, goal=goal):
                log = self.base / "codex.log"
                log.unlink(missing_ok=True)
                body = codex_body(log, status=status if status is not None else {}, goal=goal)
                self.configure({"codex": self.fake("codex", body)})
                self.refused("probe", "--host", "codex", "--session", SESSION)
                self.assertNotIn("thread/resume", log.read_text())
        self.assertFalse((self.root / "state/context" / ctx.filename(SESSION, "codex")).exists())

    def test_codex_refuses_an_archived_or_other_thread_and_error_replies(self):
        for thread in ({"id": SESSION, "status": {"type": "idle"}, "archived": True},
                       {"id": "00000000-0000-4000-8000-0000000000b2", "status": {"type": "idle"}}):
            with self.subTest(thread=thread):
                log = self.base / "codex.log"
                log.unlink(missing_ok=True)
                body = codex_body(log).replace(
                    f"put({{'id':2,'result':{{'thread':{{'id':{SESSION!r},'status':{{'type': 'idle'}}}}}}}})",
                    f"put({{'id':2,'result':{{'thread':{thread!r}}}}})")
                self.assertIn(repr(thread), body)
                self.configure({"codex": self.fake("codex", body)})
                self.refused("probe", "--host", "codex", "--session", SESSION)
                self.assertNotIn("thread/resume", log.read_text())
        log = self.base / "codex.log"
        body = codex_body(log).replace("put({'id':4,'result':{}})", "put({'id':4,'error':{'code':1}})")
        self.configure({"codex": self.fake("codex", body)})
        self.refused("probe", "--host", "codex", "--session", SESSION)

    def test_timeout_output_cap_and_early_exit_fail_closed(self):
        self.configure({"codex": self.fake("codex", "import time\ntime.sleep(60)\n")})
        started = time.monotonic()
        with mock.patch.object(ctx, "PROBE_TIMEOUT", .2):
            self.refused("probe", "--host", "codex", "--session", SESSION)
        self.assertLess(time.monotonic() - started, 10)
        self.configure({"codex": self.fake("codex", "print('x'*70000)\n")})
        self.refused("probe", "--host", "codex", "--session", SESSION)
        self.configure({"codex": self.fake("codex", "")})
        self.refused("probe", "--host", "codex", "--session", SESSION)
        self.configure({"claude": self.claude("x" * 70000)})
        self.refused("probe", "--host", "claude", "--session", SESSION)

    def test_off_unconfirmed_or_invalid_input_never_runs_a_program(self):
        entry = self.claude()
        self.configure({"claude": entry})
        with mock.patch.dict(os.environ, {"FNL_CONTEXT_PROBE": "off"}):
            self.refused("probe", "--host", "claude", "--session", SESSION)
        for session in ("synthetic", "../" + SESSION, SESSION + "0", SESSION.upper() + "\n", ""):
            self.refused("probe", "--host", "claude", "--session", session)
        self.refused("probe", "--host", "antigravity", "--session", SESSION)
        self.refused("probe", "--host", "claude")
        self.configure({"claude": entry}, confirmed=False)
        self.refused("probe", "--host", "claude", "--session", SESSION)
        self.configure({"claude": entry}, quota="off")
        self.refused("probe", "--host", "claude", "--session", SESSION)
        self.refused("probe", "--host", "codex", "--session", SESSION)
        moved = dict(entry, resolved=str(self.bin / "elsewhere"))
        self.configure({"claude": moved})
        self.refused("probe", "--host", "claude", "--session", SESSION)
        self.assertFalse(self.seen.exists())

    def test_no_hook_runs_the_probe(self):
        for path in ROOT.glob(".*-plugin/hooks.json"):
            with self.subTest(path=path.parent.name):
                self.assertNotIn("probe", path.read_text().replace("quota_probe", ""))
        for path in (ROOT / "scripts").glob("*.py"):
            if path.name != "context_snapshot.py":
                with self.subTest(script=path.name):
                    self.assertNotIn("context_snapshot.py probe", path.read_text())


if __name__ == "__main__":
    unittest.main()
