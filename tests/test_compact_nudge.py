"""Compaction nudge: synthetic homes, settings, transcripts and environments only."""
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import compact_nudge as cn
import compact_setup
import data_root as dr

SESSION = "00000000-0000-4000-8000-0000000000b2"
SECRET = "SYNTHETIC-CONTENT-7f3a"
WINDOW = 1000000


def message(percent):
    return cn.MESSAGE.format(percent)


class CompactNudgeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.home = account(self, self.base / "home")
        self.config = self.home / ".claude"
        self.projects = self.config / "projects" / "-synthetic-repo"
        self.projects.mkdir(parents=True)
        self.repo = self.base / "repo"
        (self.repo / ".git").mkdir(parents=True)
        self.managed = self.base / "managed" / "managed-settings.json"
        for patch in (mock.patch.dict(os.environ, {}, clear=True),
                      mock.patch.object(compact_setup, "managed_settings",
                                        return_value=[("managed", self.managed)])):
            patch.start()
            self.addCleanup(patch.stop)
        self.transcript = self.projects / (SESSION + ".jsonl")
        self.settings("user", {"autoCompactWindow": WINDOW})

    def settings(self, scope, data):
        path = {"user": self.config / "settings.json", "project": self.repo / ".claude/settings.json",
                "local": self.repo / ".claude/settings.local.json", "managed": self.managed}[scope]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data))
        return path

    def turn(self, used, path=None, text=SECRET):
        usage = {"input_tokens": used // 2, "cache_creation_input_tokens": 1,
                 "cache_read_input_tokens": used - used // 2 - 2, "output_tokens": 1}
        entry = {"type": "assistant", "sessionId": SESSION, "cwd": str(self.repo),
                 "message": {"role": "assistant", "content": [{"type": "text", "text": text}], "usage": usage}}
        with open(path or self.transcript, "a") as stream:
            stream.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
            stream.write(json.dumps(entry) + "\n")

    def run_hook(self, transcript=None, env=None, events=None):
        event = {"hook_event_name": "UserPromptSubmit", "session_id": SESSION, "cwd": str(self.repo),
                 "transcript_path": str(transcript or self.transcript), "prompt": SECRET}
        out = []
        real_write = os.write

        def write(fd, data):
            if fd == 1:
                out.append(data)
                if events is not None:
                    events.append("print")
                return len(data)
            return real_write(fd, data)

        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(event).encode()))
        with mock.patch.dict(os.environ, env or {}), mock.patch.object(sys, "stdin", stdin), \
                mock.patch.object(os, "write", side_effect=write):
            self.assertEqual(cn.main(), 0)
        return b"".join(out).decode()

    def mark_folder(self):
        return self.home / ".finolabs/vibecode/state/compaction-nudge"

    def mark(self):
        return self.mark_folder() / cn.hashlib.sha256(SESSION.encode()).hexdigest()[:16]

    # Bands and reset

    def test_bands_print_once_each_and_reset_after_a_drop(self):
        for used, expected in ((790000, ""), (800000, message(80)), (850000, ""), (890000, ""),
                               (900000, message(90)), (950000, ""),
                               (100000, ""), (790000, ""), (800000, message(80)), (900000, message(90))):
            with self.subTest(used=used):
                self.turn(used)
                self.assertEqual(self.run_hook(), expected)

    def test_message_is_fixed_and_names_session_hygiene(self):
        self.turn(810000)
        output = self.run_hook()
        self.assertEqual(output, message(81))
        self.assertIn("run tidy now", output)
        self.assertTrue(output.isascii())

    def test_off_switch_prints_nothing(self):
        self.turn(950000)
        self.assertEqual(self.run_hook(env={"FNL_COMPACT_NUDGE": "off"}), "")
        self.assertFalse(self.mark().exists())

    # Transcript reading

    def test_symlinked_transcript_prints_nothing(self):
        for target in (self.base / "outside.jsonl", self.projects / "real.jsonl"):
            with self.subTest(target=target.name):
                self.turn(950000, target)
                link = self.projects / ("link-" + target.name)
                link.symlink_to(target)
                self.assertEqual(self.run_hook(link), "")
        self.assertFalse(self.mark().exists())

    def test_path_outside_projects_prints_nothing(self):
        for path in (self.base / "other" / "x.jsonl", self.config / "x.jsonl", self.home / "projects" / "x.jsonl"):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                self.turn(950000, path)
                self.assertEqual(self.run_hook(path), "")
        self.assertEqual(self.run_hook(self.projects / ".." / ".." / "x.jsonl"), "")

    def test_config_dir_variable_selects_the_projects_folder(self):
        other = self.base / "work-config"
        (other / "projects/p").mkdir(parents=True)
        (other / "settings.json").write_text(json.dumps({"autoCompactWindow": WINDOW}))
        self.turn(950000)
        self.assertEqual(self.run_hook(env={"CLAUDE_CONFIG_DIR": str(other)}), "")
        inside = other / "projects/p" / "t.jsonl"
        self.turn(950000, inside)
        self.assertEqual(self.run_hook(inside, env={"CLAUDE_CONFIG_DIR": str(other)}), message(95))

    def test_large_file_is_read_only_at_its_tail(self):
        self.turn(950000)  # only at the head, beyond the tail window
        filler = json.dumps({"type": "user", "message": {"role": "user", "content": "x" * 1000}}) + "\n"
        with open(self.transcript, "a") as stream:
            stream.write(filler * (10 * 1024 * 1024 // len(filler) + 1))
        self.assertGreater(self.transcript.stat().st_size, 10 * 1024 * 1024)
        real_read, sizes = os.read, []

        def read(fd, n):
            data = real_read(fd, n)
            sizes.append(len(data))
            return data

        with mock.patch.object(os, "read", side_effect=read):
            self.assertEqual(self.run_hook(), "")
        self.assertLessEqual(sum(sizes), cn.TAIL + 4096)  # the tail plus the small synthetic settings file
        tail = cn.transcript_tail(str(self.transcript), self.config / "projects")
        self.assertLessEqual(len(tail), cn.TAIL)
        self.turn(820000)
        self.assertEqual(self.run_hook(), message(82))

    def test_content_beside_usage_never_reaches_output_or_mark(self):
        self.turn(930000, text=SECRET)
        output = self.run_hook()
        self.assertEqual(output, message(93))
        self.assertNotIn(SECRET, output)
        self.assertEqual(self.mark().read_text(), "90")
        self.assertNotIn(SECRET.encode(), b"".join(p.read_bytes() for p in self.mark_folder().iterdir()))

    def test_invalid_usage_shapes_are_skipped(self):
        bad = [{"type": "assistant", "message": {"usage": {"input_tokens": "900000", "output_tokens": 1,
                                                            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
               {"type": "assistant", "message": {"usage": {"input_tokens": -1, "output_tokens": 1,
                                                            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
               {"type": "assistant", "message": {"usage": {"input_tokens": 900000}}},
               {"type": "user", "message": {"usage": {"input_tokens": 900000, "output_tokens": 0,
                                                      "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
               {"type": "assistant", "message": "text"}]
        with open(self.transcript, "w") as stream:
            for entry in bad:
                stream.write(json.dumps(entry) + "\n")
            stream.write("{not json\n")
        self.assertEqual(self.run_hook(), "")
        self.turn(800000)
        with open(self.transcript, "a") as stream:
            stream.write(json.dumps(bad[0]))  # an incomplete last line is ignored
        self.assertEqual(self.run_hook(), message(80))

    # Threshold resolution

    def threshold(self, env=None):
        environ = env or {}
        return cn.threshold(environ, cn.settings_values(cn.settings_files(environ, str(self.repo))))

    def test_threshold_precedence(self):
        self.assertEqual(self.threshold(), WINDOW)
        self.settings("project", {"autoCompactWindow": 600000})
        self.assertEqual(self.threshold(), 600000)
        self.settings("local", {"autoCompactWindow": 500000})
        self.assertEqual(self.threshold(), 500000)
        self.settings("managed", {"autoCompactWindow": 400000})
        self.assertEqual(self.threshold(), 400000)
        self.assertEqual(self.threshold({"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300000"}), 300000)

    def test_no_window_prints_nothing_until_the_host_default_is_recorded(self):
        (self.config / "settings.json").unlink()
        self.assertIsNone(self.threshold())
        self.turn(990000)
        self.assertEqual(self.run_hook(), "")

    def test_auto_compaction_off(self):
        for env in ({"DISABLE_AUTO_COMPACT": "1"}, {"DISABLE_AUTO_COMPACT": "true"}):
            with self.subTest(env=env):
                self.assertIsNone(self.threshold(env))
        self.assertEqual(self.threshold({"DISABLE_AUTO_COMPACT": "0"}), WINDOW)
        self.settings("user", {"autoCompactWindow": WINDOW, "autoCompactEnabled": False})
        self.assertIsNone(self.threshold())
        self.turn(990000)
        self.assertEqual(self.run_hook(), "")
        # The most specific file that sets it wins.
        self.settings("local", {"autoCompactEnabled": True})
        self.assertEqual(self.threshold(), WINDOW)
        self.settings("managed", {"autoCompactEnabled": False})
        self.assertIsNone(self.threshold())

    def test_override_percent_lowers_the_threshold(self):
        self.assertEqual(self.threshold({"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"}), 500000)
        for value in ("0", "150", "abc", "50%", "-5", ""):
            with self.subTest(value=value):
                self.assertEqual(self.threshold({"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": value}), WINDOW)
        self.turn(420000)
        self.assertEqual(self.run_hook(env={"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"}), message(84))

    def test_invalid_values_are_ignored(self):
        self.settings("project", "{not json")
        for value in ("big", -5, True, 10 ** 12, 999, 1.5e6, None, [WINDOW]):
            with self.subTest(value=value):
                self.settings("local", {"autoCompactWindow": value})
                self.assertEqual(self.threshold(), WINDOW)
        for value in ("big", "-5", "1e6", "999", "99999999999"):
            with self.subTest(env=value):
                self.assertEqual(self.threshold({"CLAUDE_CODE_AUTO_COMPACT_WINDOW": value}), WINDOW)
        self.settings("local", {"autoCompactEnabled": "false"})
        self.assertEqual(self.threshold(), WINDOW)

    def test_settings_symlink_is_not_read(self):
        real = self.base / "real-settings.json"
        real.write_text(json.dumps({"autoCompactWindow": 200000}))
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.local.json").symlink_to(real)
        self.assertEqual(self.threshold(), WINDOW)

    # Mark

    def test_mark_is_written_before_the_print(self):
        events = []
        real = dr.atomic_write

        def write(folder, name, data):
            real(folder, name, data)
            events.append("mark")

        self.turn(800000)
        with mock.patch.object(dr, "atomic_write", side_effect=write):
            self.assertEqual(self.run_hook(events=events), message(80))
        self.assertEqual(events, ["mark", "print"])
        info = self.mark().lstat()
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        self.assertEqual(self.mark().read_text(), "80")

    def test_unwritable_mark_prints_nothing(self):
        self.turn(950000)
        with mock.patch.object(dr, "atomic_write", side_effect=OSError("synthetic")):
            self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.mark().exists())

    def test_unsafe_mark_prints_nothing(self):
        self.turn(950000)
        self.assertEqual(self.run_hook(), message(95))
        self.mark().chmod(0o644)
        self.turn(100000)
        self.turn(950000)
        self.assertEqual(self.run_hook(), "")

    def test_mark_resets_on_a_drop(self):
        self.turn(900000)
        self.assertEqual(self.run_hook(), message(90))
        self.turn(200000)
        self.assertEqual(self.run_hook(), "")
        self.assertEqual(self.mark().read_text(), "0")
        self.turn(810000)
        self.assertEqual(self.run_hook(), message(81))

    def test_eviction_keeps_at_most_200_marks_oldest_first(self):
        with dr.data_folder(cn.FOLDER, create=True, private=True) as folder:
            for index in range(cn.MAX_MARKS):
                dr.atomic_write(folder, f"{index:016x}", b"1")
        for index in range(cn.MAX_MARKS):
            os.utime(self.mark_folder() / f"{index:016x}", (1000000 + index, 1000000 + index))
        self.turn(800000)
        self.assertEqual(self.run_hook(), message(80))
        names = {p.name for p in self.mark_folder().iterdir()}
        self.assertEqual(len(names), cn.MAX_MARKS)
        self.assertNotIn(f"{0:016x}", names)
        self.assertIn(f"{1:016x}", names)
        self.assertIn(self.mark().name, names)


class ManifestTest(unittest.TestCase):
    def test_nudge_has_its_own_group_and_always_exits_zero(self):
        groups = json.loads((ROOT / ".claude-plugin/hooks.json").read_text())["hooks"]["UserPromptSubmit"]
        mine = [g for g in groups if any("compact_nudge.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(mine), 1)
        self.assertEqual(len(mine[0]["hooks"]), 1)
        self.assertNotIn("matcher", mine[0])
        hook = mine[0]["hooks"][0]
        self.assertTrue(hook["command"].endswith("; exit 0"))
        self.assertTrue(hook["command"].startswith("python3 -I "))
        self.assertFalse(hook.get("async", False))
        for group in groups:
            if group is not mine[0]:
                self.assertFalse(any("compact_nudge.py" in h["command"] for h in group["hooks"]))
        for host in ("codex", "antigravity"):
            path = ROOT / f".{host}-plugin/hooks.json"
            if path.exists():
                self.assertNotIn("compact_nudge.py", path.read_text())

    def test_script_exits_zero_silently_on_any_input(self):
        command = json.loads((ROOT / ".claude-plugin/hooks.json").read_text())["hooks"]["UserPromptSubmit"][-1]["hooks"][0]["command"]
        with tempfile.TemporaryDirectory() as tmp:
            home = account(self, Path(tmp) / "home")
            for raw in (b"", b"{malformed\xff", b"x" * (2 * 1024 * 1024), b"[]",
                        json.dumps({"session_id": SESSION, "transcript_path": 5}).encode()):
                with self.subTest(size=len(raw)):
                    result = subprocess.run(["sh", "-c", command], input=raw, capture_output=True, timeout=10,
                                            env={"PATH": os.defpath, "CLAUDE_PLUGIN_ROOT": str(ROOT),
                                                 "HOME": str(home)})
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_any_exception_in_main_exits_zero(self):
        with mock.patch.object(cn, "threshold", side_effect=RuntimeError("synthetic")), \
                mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(
                    {"session_id": SESSION, "transcript_path": "/x"}).encode()))), \
                mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(cn, "settings_files", return_value=[]):
            self.assertEqual(cn.main(), 0)


if __name__ == "__main__":
    unittest.main()
