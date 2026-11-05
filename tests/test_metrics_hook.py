"""Tests for scripts/metrics_hook.py, run as a subprocess the way Claude Code runs it."""

import importlib.util
import itertools
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from tests.data_root_fixture import account
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts/metrics_hook.py"

spec = importlib.util.spec_from_file_location("fnl_metrics", ROOT / "scripts/fnl_metrics.py")
fm = importlib.util.module_from_spec(spec)
sys.modules["fnl_metrics"] = fm
spec.loader.exec_module(fm)

MARKER = "<!-- fnl-review kind=code head=0123456789abcdef0123456789abcdef01234567 verdict=REWORK -->"


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / "home")
        self.dir = self.home / ".finolabs/vibecode/state"
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / ".git").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(self.dir)})  # in-process calls must never reach the real state
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env = {**os.environ, "FNL_STATE_DIR": str(self.dir)}
        self.env.pop("FNL_METRICS", None)
        self.env.pop("FNL_DISPATCH_ID", None)

    def consent(self, days=90):
        fm.write_consent(days)

    def run_hook(self, payload, env=None, raw=None, args=(), stdout=""):
        result = subprocess.run([sys.executable, "-I", str(HOOK), *args], input=raw if raw is not None else json.dumps(payload),
                                capture_output=True, text=True, env=env or self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, stdout)
        return result

    def post(self, tool, tool_input, **extra):
        return self.run_hook({"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo),
                              "tool_name": tool, "tool_input": tool_input, **extra})

    def events(self):
        return [json.loads(line) for path in sorted(self.dir.glob("events-*.jsonl")) for line in path.read_text().splitlines()]

    def test_nothing_is_recorded_without_consent(self):
        self.post("Skill", {"skill": "fnl-coding-router"})
        self.assertFalse(self.dir.exists())

    def test_a_skill_and_an_agent_are_recorded_by_their_fnl_name(self):
        self.consent()
        self.post("Skill", {"skill": "finolabs-vibecode:fnl-coding-router"})
        self.post("Agent", {"subagent_type": "finolabs-vibecode:fnl-reviewer", "prompt": "secret task text"})
        self.post("Skill", {"skill": "grilling"})
        self.post("Agent", {"subagent_type": "Explore"})
        got = [(e["event"], e["name"]) for e in self.events()]
        self.assertEqual(got, [("skill", "fnl-coding-router"), ("agent", "fnl-reviewer")])

    def test_only_the_first_edit_of_a_session_is_recorded(self):
        self.consent()
        for tool in ("Edit", "Write", "Edit"):
            self.post(tool, {"file_path": "/private/path/secret.py", "content": "secret"})
        self.assertEqual([e["event"] for e in self.events()], ["first_edit"])

    def test_a_commit_is_found_in_compound_commands_and_never_stores_the_text(self):
        self.consent()
        self.post("Bash", {"command": "cd repo && git add a && git -c user.name=x commit -q -m 'api key hunter2'"})
        self.post("Bash", {"command": "git log --grep=commit"})
        self.post("Bash", {"command": "git commit-tree abc"})
        self.post("Bash", {"command": "ls"})
        self.assertEqual([e["event"] for e in self.events()], ["commit"])
        self.assertNotIn("hunter2", "".join(p.read_text() for p in self.dir.glob("events-*")))

    def test_a_review_comment_is_recorded_from_its_marker_line(self):
        self.consent()
        body = self.repo / "report.md"
        body.write_text(MARKER + "\nSecret finding text\n")
        self.post("Bash", {"command": 'gh pr comment 31 --repo o/r --body-file "report.md"'})
        [event] = self.events()
        self.assertEqual((event["event"], event["kind"], event["verdict"], event["pr"]), ("review", "code", "REWORK", 31))
        self.assertNotIn("Secret finding", json.dumps(event))

    def test_a_review_body_that_is_not_a_marker_or_is_a_symlink_is_ignored(self):
        self.consent()
        (self.repo / "plain.md").write_text("no marker here\n")
        real = self.repo / "real.md"
        real.write_text(MARKER + "\n")
        (self.repo / "link.md").symlink_to(real)
        for name in ("plain.md", "link.md", "missing.md"):
            self.post("Bash", {"command": "gh pr comment 5 --body-file " + name})
        self.post("Bash", {"command": "gh pr comment 5 --body-file -"})
        self.assertEqual(self.events(), [])

    def test_malformed_input_creates_nothing_when_not_consented_or_off(self):
        for raw in ("garbage", "", "[1"):
            self.run_hook(None, raw=raw)
        self.assertFalse(self.dir.exists())
        self.consent()
        for raw in ("garbage", ""):
            self.run_hook(None, raw=raw, env={**self.env, "FNL_METRICS": "off"})
        self.assertFalse((self.dir / "errors.count").exists())
        self.assertEqual(self.events(), [])

    def test_a_review_posted_through_a_heredoc_is_recorded_without_its_text(self):
        self.consent()
        self.post("Bash", {"command": "gh pr comment 31 --repo o/r --body-file - <<'EOF'\n" + MARKER + "\nfinding text\nEOF"})
        [event] = self.events()
        self.assertEqual((event["event"], event["verdict"], event["pr"]), ("review", "REWORK", 31))
        self.assertNotIn("finding text", "".join(p.read_text() for p in self.dir.glob("events-*")))

    def test_review_commands_with_flags_before_the_number_or_a_url_or_an_inline_body(self):
        self.consent()
        (self.repo / "r.md").write_text(MARKER + "\n")
        self.post("Bash", {"command": "gh pr comment --repo o/r 41 --body-file r.md"})
        self.post("Bash", {"command": 'gh pr comment https://github.com/o/r/pull/42 --body "' + MARKER + '\ntext"'})
        self.assertEqual([e["pr"] for e in self.events()], [41, 42])

    def test_a_pipe_named_as_the_body_file_does_not_hang_the_hook(self):
        self.consent()
        os.mkfifo(self.repo / "pipe")
        payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo), "tool_name": "Bash",
                   "tool_input": {"command": "gh pr comment 5 --body-file pipe"}}
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                                env=self.env, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])

    def test_commit_and_router_words_inside_other_commands_are_not_triggers(self):
        self.consent()
        base = "python3 -I skills/fnl-coding-router/scripts/record.py router --depth DEEP --trigger none"
        for command in ("echo git commit", 'grep "git commit" notes.txt', "grep '" + base + "' log.txt"):
            self.post("Bash", {"command": command})
        self.assertEqual(self.events(), [])
        self.post("Bash", {"command": 'git -C "dir with space" commit -q -m x'})
        self.post("Bash", {"command": "GIT_AUTHOR_NAME=x git commit -m y"})
        self.post("Bash", {"command": "cd x && " + base})
        self.post("Bash", {"command": 'git commit -m "' + base + '"'})
        self.assertEqual([e["event"] for e in self.events()], ["commit", "commit", "router", "commit"])

    def run_within(self, command, seconds=5):
        payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo), "tool_name": "Bash",
                   "tool_input": {"command": command}}
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                                env=self.env, timeout=seconds)
        self.assertEqual(result.returncode, 0)

    def test_commands_built_to_make_the_patterns_backtrack_finish_quickly(self):
        self.consent()
        self.run_within("git " + '-c "a" ' * 60 + "status")
        self.run_within(";" * 20000)
        self.run_within("git " + "-c a " * 3000 + "status")
        self.assertEqual(self.events(), [])

    def test_a_trigger_inside_an_overlong_command_is_not_tested(self):
        self.consent()
        self.post("Bash", {"command": "echo " + "x" * 9000 + "\ngit commit -m y"})
        self.assertEqual(self.events(), [])

    def test_a_quoted_script_path_the_cat_heredoc_idiom_and_two_comments_are_recorded(self):
        self.consent()
        approve = MARKER.replace("kind=code", "kind=security").replace("verdict=REWORK", "verdict=APPROVE")
        self.post("Bash", {"command": 'python3 -I "/a/b/scripts/record.py" router --depth MIN --trigger none'})
        self.post("Bash", {"command": "gh pr comment 5 --body \"$(cat <<'EOF'\n" + MARKER + "\ntext\nEOF\n)\""})
        self.post("Bash", {"command": "gh pr comment 6 --body-file - <<'A'\n" + MARKER + "\nA\ngh pr comment 7 --body-file - <<'B'\n" + approve + "\nB"})
        got = [(e["event"], e.get("pr"), e.get("verdict")) for e in self.events()]
        self.assertEqual(got, [("router", None, None), ("review", 5, "REWORK"), ("review", 6, "REWORK"), ("review", 7, "APPROVE")])

    def agy(self, event, call=None):
        """An Antigravity payload in the shape a real `agy` run sent: camelCase, no event name, a toolCall for tool hooks."""
        payload = {"conversationId": "31357bed-2c92-4bc3-ad3d-23c9545c7b3e", "workspacePaths": [str(self.repo)], "modelName": "m",
                   "transcriptPath": "t", "artifactDirectoryPath": "a", "lastUserInput": "u"}
        if call:
            payload.update({"stepIdx": 2, "error": "", "toolCall": call})
        return self.run_hook(payload, args=("--host", "antigravity", "--event", event), stdout="{}\n")

    def test_an_antigravity_session_is_recorded_from_its_own_payload_shape(self):
        self.consent()
        self.agy("session_start")
        self.agy("post_tool_use", {"name": "write_file", "args": {"Content": "hi\n", "Path": str(self.repo / "hello.txt")}})
        self.agy("post_tool_use", {"name": "replace_file_content", "args": {"TargetFile": "x"}})
        self.agy("post_tool_use", {"name": "run_command", "args": {"CommandLine": "git commit -q -m x", "Cwd": str(self.repo)}})
        self.agy("post_tool_use", {"name": "view_file", "args": {"Path": "x"}})
        started, edited, committed = self.events()
        self.assertEqual((started["event"], started["host"], started["source"]), ("session_start", "antigravity", "startup"))
        self.assertEqual(started["sid"], "31357bed-2c92-4bc3-ad3d-23c9545c7b3e")
        self.assertEqual((edited["event"], committed["event"]), ("first_edit", "commit"))

    def test_an_antigravity_session_start_does_not_wait_for_a_dashboard_refresh(self):
        self.consent()
        self.agy("session_start")
        self.assertFalse((self.dir / "data.js").exists())

    def test_an_antigravity_hook_still_answers_with_an_empty_object_when_off_or_given_garbage(self):
        self.run_hook(None, raw="garbage", args=("--host", "antigravity", "--event", "post_tool_use"), stdout="{}\n")
        self.assertFalse(self.dir.exists())
        self.consent()
        self.run_hook(None, raw="garbage", args=("--host", "antigravity", "--event", "post_tool_use"), stdout="{}\n")
        self.run_hook(None, raw="{}", args=("--host", "antigravity", "--event", "post_tool_use"),
                      env={**self.env, "FNL_METRICS": "off"}, stdout="{}\n")
        self.assertEqual(self.events(), [])

    def test_a_codex_session_uses_its_edit_tool_and_may_send_a_command_as_an_array(self):
        self.consent()
        base = {"session_id": "codex-1", "cwd": str(self.repo), "model": "m", "transcript_path": None}
        self.run_hook({**base, "hook_event_name": "SessionStart", "source": "resume", "permission_mode": "default"}, args=("--host", "codex"))
        self.run_hook({**base, "hook_event_name": "PostToolUse", "tool_name": "apply_patch", "tool_use_id": "u", "turn_id": "t",
                       "tool_input": {"command": "*** Begin Patch"}, "tool_response": {}}, args=("--host", "codex"))
        self.run_hook({**base, "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": ["git", "commit", "-m", "x"]}},
                      args=("--host", "codex"))
        started, edited, committed = self.events()
        self.assertEqual((started["host"], started["source"]), ("codex", "resume"))
        self.assertEqual((edited["event"], committed["event"]), ("first_edit", "commit"))

    def test_the_codex_command_runs_nothing_and_exits_zero_when_no_root_variable_is_set(self):
        config = json.loads((ROOT / ".codex-plugin/hooks.json").read_text())
        commands = {h["command"] for groups in config["hooks"].values() for g in groups for h in g["hooks"]}
        [metrics] = [c for c in commands if "metrics_hook.py" in c]  # the other hooks are independent reminders and checks
        bare = {"PATH": os.environ["PATH"]}
        for command in commands:
            self.assertEqual(subprocess.run(["sh", "-c", command], input="{}", env=bare, capture_output=True, text=True).returncode, 0)
        self.consent()
        result = subprocess.run(["sh", "-c", metrics], input=json.dumps({"hook_event_name": "SessionStart", "session_id": "c1", "cwd": str(self.repo)}),
                                env={**self.env, "PLUGIN_ROOT": str(ROOT)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual([e["host"] for e in self.events()], ["codex"])

    def test_every_shipped_hook_command_ends_with_exit_zero(self):
        for name in (".claude-plugin/hooks.json", ".codex-plugin/hooks.json"):
            config = json.loads((ROOT / name).read_text())
            for groups in config["hooks"].values():
                for group in groups:
                    for hook in group["hooks"]:
                        self.assertRegex(hook["command"], r"; exit 0\s*$", name + ": " + hook["command"])

    def test_no_plugin_root_hooks_file_is_shipped_for_antigravity(self):
        self.assertFalse((ROOT / "hooks.json").exists(), "see the spec: its working folder on a real install is unverified")

    def test_a_closed_output_pipe_does_not_break_the_exit_code(self):
        spec = importlib.util.spec_from_file_location("metrics_hook_under_test", HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(sys, "argv", ["metrics_hook.py", "--host", "antigravity", "--event", "post_tool_use"]), \
                mock.patch("builtins.print", side_effect=BrokenPipeError), mock.patch.object(sys, "stdin", mock.Mock(read=lambda: "")):
            module.main()

    def test_a_command_made_to_slow_the_regexes_is_dismissed_by_the_cheap_checks(self):
        self.consent()
        self.run_within("a=;" * 2700)
        self.run_within(";a=a" * 2000)
        self.assertEqual(self.events(), [])

    def test_an_unknown_host_is_recorded_as_other(self):
        self.consent()
        self.run_hook({"hook_event_name": "SessionStart", "session_id": "s9", "cwd": str(self.repo), "source": "startup"},
                      args=("--host", "somewhere-else"))
        self.assertEqual(self.events()[0]["host"], "other")

    def test_the_router_receipt_command_is_recorded_with_its_depth_and_trigger(self):
        self.consent()
        base = "python3 -I skills/fnl-coding-router/scripts/record.py router "
        self.post("Bash", {"command": base + "--depth DEEP --trigger security"})
        self.post("Bash", {"command": base + "--depth HUGE --trigger security"})
        self.post("Bash", {"command": base + "--depth MIN --trigger made-up"})
        [event] = self.events()
        self.assertEqual((event["event"], event["depth"], event["trigger"]), ("router", "DEEP", "security"))

    def test_the_router_receipt_command_prints_one_line_and_rejects_a_bad_value(self):
        record = ROOT / "skills/fnl-coding-router/scripts/record.py"
        ok = subprocess.run([sys.executable, "-I", str(record), "router", "--depth", "NORMAL", "--trigger", "none"],
                            capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "router receipt: depth=NORMAL trigger=none"))
        bad = subprocess.run([sys.executable, "-I", str(record), "router", "--depth", "HUGE", "--trigger", "none"],
                             capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)

    def test_the_keep_receipt_command_is_recorded_with_fixed_values_only(self):
        self.consent()
        base = 'python3 -I "/a/skills/fnl-delegate/scripts/record.py" keep '
        self.post("Bash", {"command": base + "--tasks 3 --reason needs-context"})
        self.post("Bash", {"command": base + "--tasks=2 --reason=user-choice --route-by=user"})
        self.post("Bash", {"command": base + "--tasks 0 --reason needs-context"})
        self.post("Bash", {"command": base + "--tasks 3 --reason because-the-parser-is-hard"})
        self.post("Bash", {"command": base + "--tasks 3 --reason no-delegate --route-by me"})
        self.post("Bash", {"command": "echo record.py keep --tasks 3 --reason no-delegate"})
        got = [(e["event"], e["tasks"], e["reason"], e["route_by"]) for e in self.events()]
        self.assertEqual(got, [("kept", 3, "needs-context", "table"), ("kept", 2, "user-choice", "user")])
        self.assertEqual(set(self.events()[0]), {"ts", "sid", "repo", "event", "tasks", "reason", "route_by"})

    def test_invalid_route_by_never_defaults_to_table(self):
        self.consent()
        keep = "python3 -I record.py keep --tasks 3 --reason no-delegate "
        for value in ("route-judge", "user1", "USER", "table_extra"):
            with self.subTest(route_by=value):
                self.post("Bash", {"command": keep + "--route-by " + value})
                self.post("Bash", {"command": keep + "--route-by=" + value})
                self.assertEqual(self.events(), [])

    def test_judge_receipts_record_on_each_host_and_respect_consent(self):
        command = "python3 -I skills/fnl-delegate/scripts/record.py judge --site route --grader judge --result validated --followed yes"
        self.post("Bash", {"command": command})
        self.assertEqual(self.events(), [])
        self.consent()
        self.post("Bash", {"command": command})
        self.run_hook({"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo),
                       "tool_name": "Bash", "tool_input": {"command": command.split()}}, args=("--host", "codex"))
        self.agy("post_tool_use", {"name": "run_command", "args": {"CommandLine": command}})
        self.assertEqual(len(self.events()), 3)
        for event in self.events():
            self.assertEqual({k: event[k] for k in ("event", "site", "grader", "result", "followed")},
                             dict(event="judge", site="route", grader="judge", result="validated", followed="yes"))
        self.run_hook({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Bash",
                       "tool_input": {"command": command}}, env={**self.env, "FNL_METRICS": "off"})
        self.assertEqual(len(self.events()), 3)

    def test_low_dollar_in_unrelated_command_keeps_judge_receipt(self):
        self.consent()
        command = "python3 -I record.py judge --site route --grader judge --result validated --followed yes"
        self.post("Bash", {"command": 'printf "%s" "$PWD"; ' + command})
        self.assertEqual([e["event"] for e in self.events()], ["judge"])
        self.post("Bash", {"command": command.replace("--site route", "--site $SITE")})
        self.post("Bash", {"command": 'echo "$(' + command + ')"'})
        self.assertEqual(len(self.events()), 1)

    def test_judge_malformed_and_quoted_commands_never_record(self):
        self.consent()
        command = "python3 -I record.py judge --site route --grader judge --result validated --followed yes"
        bad = [command.replace("--site route", "--site free-text"), command.replace("--followed yes", ""),
               command.replace("--grader judge", "--grader agent"),
               command.replace("--result validated", "--result unverified"),
               command.replace("--grader judge", "--grader agent").replace("--result validated", "--result unverified").replace("--followed yes", "--followed na"),
               command + " --extra secret", command + " --site depth", command + " trailing",
               command.replace("record.py", '"record.py'), command.replace("record.py", "'record.py"),
               "# ignored; " + command, ["echo", "line; " + command],
               command.replace("--site", "--sit"), command.replace("record.py", "myrecord.py"),
               command + " '", "echo '" + command + "'", 'echo "' + command + '"',
               "echo 'line; " + command + "'", "echo 'line\n" + command + "'",
               "message='\n" + command + "'", '"' + command + '"',
               "cat <<'EOF'\n" + command + "\nEOF"]
        for text in bad:
            with self.subTest(command=text):
                self.post("Bash", {"command": text})
                self.assertEqual(self.events(), [])
        self.post("Bash", {"command": "cd repo && " + command + "; " + command.replace("--site route", "--site=depth")})
        self.assertEqual([e["site"] for e in self.events()], ["route", "depth"])

    def test_judge_receipt_copies_accept_the_same_values_and_pairs_without_writes(self):
        records = [ROOT / ("skills/" + skill + "/scripts/record.py") for skill in ("fnl-delegate", "fnl-coding-router")]
        cases = list(itertools.product(("route", "depth", "activity", "instruction"), ("judge", "agent"),
                                       ("validated", "unverified"), ("yes", "no", "na")))
        cases += [("free text", "judge", "validated", "yes"), ("route", "other", "validated", "yes"),
                  ("route", "judge", "invalid", "na"), ("route", "judge", "validated", "maybe")]
        for site, grader, result, followed in cases:
            valid = (site in fm.JUDGE_SITES and grader in fm.JUDGE_GRADERS and result in fm.JUDGE_RESULTS
                     and followed in fm.JUDGE_FOLLOWED and
                     (grader == "judge" and (result == "validated" or followed == "na")
                      or grader == "agent" and result == "validated" and followed == "na"))
            outputs = []
            for record in records:
                done = subprocess.run([sys.executable, "-I", str(record), "judge", "--site", site, "--grader", grader,
                                       "--result", result, "--followed", followed], capture_output=True, text=True,
                                      cwd=self.repo, env={**self.env, "FNL_AUTO_GATE": "on"})
                outputs.append((done.returncode, done.stdout))
                self.assertEqual(done.returncode == 0, valid, (record, site, grader, result, followed))
                if valid:
                    self.assertEqual(done.stdout, "judge receipt: site=%s grader=%s result=%s followed=%s\n" %
                                     (site, grader, result, followed))
                    self.assertEqual(done.stderr, "")
            self.assertEqual(outputs[0], outputs[1])
        self.assertFalse(self.dir.exists())
        self.assertEqual(list(self.repo.iterdir()), [self.repo / ".git"])

    def test_the_keep_receipt_is_not_recorded_without_consent(self):
        self.post("Bash", {"command": "python3 -I record.py keep --tasks 3 --reason needs-context"})
        self.assertEqual(self.events(), [])

    def test_the_keep_receipt_command_prints_one_line_and_offers_the_schema_values(self):
        record = ROOT / "skills/fnl-delegate/scripts/record.py"
        ok = subprocess.run([sys.executable, "-I", str(record), "keep", "--tasks", "2", "--reason", "no-delegate"],
                            capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "keep receipt: tasks=2 reason=no-delegate route_by=table"))
        for bad in (["--tasks", "0", "--reason", "no-delegate"], ["--tasks", "2", "--reason", "other"],
                    ["--tasks", "2", "--reason", "no-delegate", "--route-by", "me"], ["--task", "2", "--rea", "no-delegate"]):
            self.assertNotEqual(subprocess.run([sys.executable, "-I", str(record), "keep", *bad], capture_output=True).returncode, 0, bad)
        spec = importlib.util.spec_from_file_location("fnl_keep_record", record)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual((module.REASONS, module.ROUTE_BY), (fm.KEPT_REASONS, fm.ROUTE_BY))

    def test_each_keep_receipt_is_read_from_its_own_arguments(self):
        self.consent()
        keep = 'python3 -I /a/scripts/record.py keep '
        start = 'python3 -I /a/scripts/ledger.py start --reason routing --route-by judge --budget 5 --tasks 7 && '
        self.post("Bash", {"command": keep + "--tasks 2 --reason needs-context && " + keep + "--tasks 1 --reason no-delegate"})
        self.post("Bash", {"command": keep + "--tasks 3 --reason hard-grade; echo done"})
        self.post("Bash", {"command": start + keep + "--tasks 4 --reason user-choice --route-by user"})
        self.post("Bash", {"command": start + keep + "--tasks 5 --reason no-delegate"})
        self.post("Bash", {"command": keep + "--tasks 6 --reason no-delegate; other --tasks 7 --reason user-choice"})
        got = [(e["tasks"], e["reason"], e["route_by"]) for e in self.events()]
        self.assertEqual(got, [(2, "needs-context", "table"), (1, "no-delegate", "table"), (3, "hard-grade", "table"),
                               (4, "user-choice", "user"), (5, "no-delegate", "table"), (6, "no-delegate", "table")])

    def test_text_that_only_looks_like_a_keep_receipt_is_not_recorded(self):
        self.consent()
        self.post("Bash", {"command": "python3 myrecord.py keep --tasks 2 --reason no-delegate"})
        self.post("Bash", {"command": "cat > note <<E\npython3 record.py keep --tasks 2 --reason no-delegate\nE"})
        self.post("Bash", {"command": "python3 record.py keep --tasks 2"})
        self.assertEqual(self.events(), [])

    def test_session_start_records_host_source_and_the_dispatch_marker(self):
        self.consent()
        self.run_hook({"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(self.repo), "source": "fork"},
                      env={**self.env, "FNL_DISPATCH_ID": "20261103-abc"})
        self.run_hook({"hook_event_name": "SessionStart", "session_id": "s2", "cwd": str(self.repo), "source": "startup"},
                      env={**self.env, "FNL_DISPATCH_ID": "bad id; rm"})
        first, second = self.events()
        self.assertEqual((first["host"], first["source"], first["dispatch"]), ("claude", "resume", "20261103-abc"))
        self.assertIsNone(second["dispatch"])

    def test_session_start_refreshes_the_dashboard_files(self):
        self.consent()
        self.run_hook({"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(self.repo), "source": "startup"})
        self.assertTrue((self.dir / "data.js").is_file())
        self.assertEqual((self.dir / "dashboard.html").read_bytes(), (ROOT / "skills/fnl-status/assets/dashboard.html").read_bytes())

    def tool_call(self, **extra):
        return {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo), "tool_name": "Bash",
                "tool_input": {"command": "ls"}, **extra}

    def test_a_tool_call_rebuilds_old_dashboard_data_and_leaves_fresh_data_alone(self):
        self.consent()
        self.run_hook(self.tool_call())
        data = self.dir / "data.js"
        fresh = data.stat().st_mtime_ns
        self.run_hook(self.tool_call())
        self.assertEqual(data.stat().st_mtime_ns, fresh, "rebuilt inside the 10 seconds")
        os.utime(data, (0, 0))
        self.run_hook(self.tool_call())
        self.assertGreater(data.stat().st_mtime, 1_000_000_000, "old data is rebuilt")

    def test_stop_and_session_start_rebuild_fresh_data(self):
        self.consent()
        self.run_hook(self.tool_call())
        data = self.dir / "data.js"
        for payload in ({"hook_event_name": "Stop", "session_id": "s1", "cwd": str(self.repo)},
                        {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(self.repo), "source": "startup"}):
            fresh = time.time() - 1  # inside the 10 second throttle: a forced rebuild must still run
            os.utime(data, (fresh, fresh))
            self.run_hook(payload)
            self.assertGreater(data.stat().st_mtime, fresh + 0.5, payload["hook_event_name"])

    def test_nothing_is_rebuilt_without_consent_or_when_turned_off(self):
        stop = {"hook_event_name": "Stop", "session_id": "s1", "cwd": str(self.repo)}
        self.run_hook(stop)
        self.run_hook(self.tool_call())
        self.assertFalse((self.dir / "data.js").exists())
        self.consent()
        off = {**self.env, "FNL_METRICS": "off"}
        self.run_hook(stop, env=off)
        self.run_hook(self.tool_call(), env=off)
        self.assertFalse((self.dir / "data.js").exists())

    def test_an_antigravity_tool_call_does_not_wait_for_a_rebuild(self):
        self.consent()
        self.agy("post_tool_use", {"name": "run_command", "args": {"CommandLine": "ls"}})
        self.assertFalse((self.dir / "data.js").exists())

    def test_the_stop_hook_is_async_on_both_hosts(self):
        for name in (".claude-plugin", ".codex-plugin"):
            config = json.loads((ROOT / name / "hooks.json").read_text())
            for group in config["hooks"]["Stop"]:
                self.assertTrue(all(h["async"] for h in group["hooks"]), name)

    def test_session_start_prunes_files_past_retention(self):
        self.consent(30)
        (self.dir / "events-2020-01.jsonl").write_text("{}\n")
        self.run_hook({"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(self.repo), "source": "startup"})
        self.assertFalse((self.dir / "events-2020-01.jsonl").exists())

    def test_bad_input_never_fails_or_prints(self):
        self.consent()
        for raw in ("", "not json", "[]", "null", json.dumps({"hook_event_name": "PostToolUse", "session_id": "../x"}),
                    json.dumps({"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Bash", "tool_input": "x"})):
            self.run_hook(None, raw=raw)

    def test_the_off_switch_stops_recording(self):
        self.consent()
        self.run_hook({"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.repo), "tool_name": "Skill",
                       "tool_input": {"skill": "fnl-x"}}, env={**self.env, "FNL_METRICS": "off"})
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
