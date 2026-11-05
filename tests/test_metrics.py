"""Tests for scripts/fnl_metrics.py: consent gating, event validation, retention and the shared copies."""

import importlib.util
import itertools
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "scripts/fnl_metrics.py"
COPIES = [ROOT / "skills/fnl-coding-router/scripts/fnl_metrics.py", ROOT / "skills/fnl-status/scripts/fnl_metrics.py",
          ROOT / "skills/fnl-update/scripts/fnl_metrics.py"]

spec = importlib.util.spec_from_file_location("fnl_metrics", CORE)
m = importlib.util.module_from_spec(spec)
sys.modules["fnl_metrics"] = m
spec.loader.exec_module(m)

SID = "sess-1"


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "state"
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / ".git").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(self.dir)})
        patcher.start()
        os.environ.pop("FNL_METRICS", None)
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def consent(self, days=90):
        m.write_consent(days)

    def events(self):
        return [json.loads(line) for path in sorted(self.dir.glob("events-*.jsonl")) for line in path.read_text().splitlines()]

    def record(self, event="skill", **fields):
        fields = fields or {"name": "fnl-coding-router"}
        return m.record(event, SID, self.repo, **fields)

    def test_nothing_is_written_without_consent(self):
        self.assertFalse(self.record())
        self.assertFalse(self.dir.exists())

    def test_the_off_switch_wins_over_consent(self):
        self.consent()
        with mock.patch.dict(os.environ, {"FNL_METRICS": "off"}):
            self.assertFalse(self.record())
        self.assertEqual(self.events(), [])

    def test_a_consented_event_is_appended_with_private_modes(self):
        self.consent()
        self.assertTrue(self.record())
        [event] = self.events()
        self.assertEqual({k: event[k] for k in ("sid", "event", "name")}, {"sid": SID, "event": "skill", "name": "fnl-coding-router"})
        self.assertRegex(event["repo"], r"^[0-9a-f]{8}$")
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode), 0o700)
        [path] = self.dir.glob("events-*.jsonl")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_an_invalid_event_is_dropped_and_counted(self):
        self.consent()
        bad = [("skill", {"name": "other-skill"}), ("skill", {"name": "fnl-x", "extra": 1}), ("skill", {}),
               ("router", {"depth": "HUGE", "trigger": "none"}), ("review", {"kind": "code", "verdict": "APPROVE", "pr": True}),
               ("nope", {})]
        for event, fields in bad:
            with self.subTest(event=event, fields=fields):
                self.assertFalse(m.record(event, SID, self.repo, **fields))
        self.assertEqual(self.events(), [])
        self.assertEqual(m.errors_count(), len(bad))

    def test_a_bad_session_id_cannot_become_a_path(self):
        self.consent()
        self.assertFalse(m.record("skill", "../escape", self.repo, name="fnl-x"))
        with self.assertRaises(ValueError):
            m.first_edit("../escape")

    def test_judge_enumerations_pairs_and_exact_fields(self):
        self.consent()
        self.assertEqual(set(m.SCHEMA.get("judge", {})), {"site", "grader", "result", "followed"})
        accepted = 0
        for site, grader, result, followed in itertools.product(
                ("route", "depth", "activity", "instruction"), ("judge", "agent"),
                ("validated", "unverified"), ("yes", "no", "na")):
            fields = dict(site=site, grader=grader, result=result, followed=followed)
            valid = (grader == "judge" and (result == "validated" or followed == "na")
                     or grader == "agent" and result == "validated" and followed == "na")
            raw = dict(ts=m.now().isoformat(timespec="milliseconds"), sid=SID, repo="12345678", event="judge", **fields)
            with self.subTest(**fields):
                self.assertEqual(m.valid_event(raw), valid)
                self.assertEqual(m.record("judge", SID, self.repo, **fields), valid)
            accepted += valid
        self.assertEqual(len(self.events()), accepted)
        good = dict(site="route", grader="judge", result="validated", followed="yes")
        bad = [{**good, key: "free text"} for key in good]
        bad += [{**good, key: "private"} for key in ("question", "answer", "cost", "file", "path", "repository")]
        bad += [{k: v for k, v in good.items() if k != key} for key in good]
        for fields in bad:
            raw = dict(ts=m.now().isoformat(timespec="milliseconds"), sid=SID, repo="12345678", event="judge", **fields)
            self.assertFalse(m.valid_event(raw))
            self.assertFalse(m.record("judge", SID, self.repo, **fields))
        self.assertEqual(len(self.events()), accepted)
        self.assertEqual(set(self.events()[0]), {"ts", "sid", "repo", "event", *good})

    def test_every_event_kind_validates(self):
        self.consent()
        cases = [("session_start", {"host": "claude", "dispatch": None, "source": "startup"}),
                 ("session_start", {"host": "codex", "dispatch": "abc123", "source": "resume"}),
                 ("agent", {"name": "fnl-reviewer"}), ("first_edit", {}), ("commit", {}),
                 ("review", {"kind": "security", "verdict": "REWORK", "pr": 31}),
                 ("router", {"depth": "DEEP", "trigger": "security"})]
        for event, fields in cases:
            with self.subTest(event=event):
                self.assertTrue(m.record(event, SID, self.repo, **fields))
        self.assertEqual(len(self.events()), len(cases))

    def test_an_unwritable_state_dir_never_raises(self):
        self.consent()
        self.dir.chmod(0o500)
        self.addCleanup(self.dir.chmod, 0o700)
        self.assertTrue(m.enabled())
        self.assertFalse(m.record("skill", SID, self.repo, name="fnl-x"))
        m.bump_errors()
        self.assertEqual(list(self.dir.glob("events-*")), [])

    def home_env(self, **extra):
        home = Path(self.tmp.name) / "home"
        home.mkdir(exist_ok=True)
        env = {"HOME": str(home), **extra}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("FNL_STATE_DIR", None)
        if "XDG_STATE_HOME" not in extra:
            os.environ.pop("XDG_STATE_HOME", None)
        return home

    def test_the_default_state_folder_is_under_the_finolabs_home(self):
        home = self.home_env()
        self.assertEqual(m.state_dir(), home / ".finolabs/vibecode/state")

    def test_a_relative_override_or_relative_xdg_state_home_is_ignored(self):
        home = self.home_env(FNL_STATE_DIR=".fnl", XDG_STATE_HOME="rel")
        self.assertEqual(m.state_dir(), home / ".finolabs/vibecode/state")

    def test_a_machine_with_only_the_older_state_folder_keeps_using_it_and_the_new_one_wins_once_it_exists(self):
        home = self.home_env(XDG_STATE_HOME=str(Path(self.tmp.name) / "xdg"))
        old = Path(self.tmp.name) / "xdg" / "finolabs-vibecode"
        old.mkdir(parents=True)
        self.assertEqual(m.state_dir(), old)
        (home / ".finolabs/vibecode/state").mkdir(parents=True)
        self.assertEqual(m.state_dir(), home / ".finolabs/vibecode/state")

    def test_folders_made_for_the_state_are_private_including_the_finolabs_home(self):
        home = self.home_env()
        m.ensure_dir(m.state_dir())
        for folder in (home / ".finolabs", home / ".finolabs/vibecode", home / ".finolabs/vibecode/state"):
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700, folder)

    def test_a_failed_write_keeps_the_error_class_but_never_its_message(self):
        self.consent()
        m.bump_errors(ValueError("secret text in /var/private/note"))
        self.assertEqual(m.errors_count(), 1)
        last = m.errors_last()
        self.assertTrue(last.endswith(" ValueError"), last)
        self.assertNotIn("secret", (self.dir / "errors.last").read_text())
        m.purge_store()
        self.assertIsNone(m.errors_last())
        self.assertEqual(m.errors_count(), 0)

    def test_a_record_that_fails_leaves_its_class_in_errors_last(self):
        self.consent()
        self.assertFalse(m.record("skill", SID, self.repo, name="not-an-fnl-name"))
        self.assertIn("ValueError", m.errors_last())

    def test_a_commondir_that_is_a_pipe_does_not_hang_the_lookup(self):
        folder = Path(self.tmp.name) / "tree"
        gitdir = Path(self.tmp.name) / "gitdir"
        folder.mkdir()
        gitdir.mkdir()
        os.mkfifo(gitdir / "commondir")
        (folder / ".git").write_text("gitdir: %s\n" % gitdir)
        self.assertEqual(m.repo_root(folder), folder.resolve())

    def test_nothing_is_created_when_metrics_are_off_or_not_consented(self):
        m.bump_errors()
        self.assertFalse(self.dir.exists())
        self.consent()
        shutil_rmtree = __import__("shutil").rmtree
        shutil_rmtree(self.dir)
        with mock.patch.dict(os.environ, {"FNL_METRICS": "off"}):
            m.bump_errors()
        self.assertFalse(self.dir.exists())

    def test_the_error_counter_counts_by_appending(self):
        self.consent()
        for _ in range(3):
            m.bump_errors()
        self.assertEqual(m.errors_count(), 3)

    def test_a_symlinked_markers_folder_is_refused_and_never_followed(self):
        self.consent()
        victim = Path(self.tmp.name) / "victim"
        victim.mkdir()
        old = victim / "old.txt"
        old.write_text("keep me")
        os.utime(old, (0, 0))
        (self.dir / "markers").symlink_to(victim)
        with self.assertRaises(ValueError):
            m.first_edit(SID)
        m.prune(30)
        self.assertEqual(m.purge_store(), 0)
        self.assertTrue(old.exists())
        self.assertEqual(sorted(p.name for p in victim.iterdir()), ["old.txt"])

    def test_prune_trims_old_lines_inside_the_month_the_cutoff_cuts_through(self):
        self.consent(30)
        keep, drop = "2026-10-31T12:00:00.000+00:00", "2026-10-01T12:00:00.000+00:00"
        line = '{"ts":"%s","sid":"s","repo":"aaaaaaaa","event":"commit"}\n'
        (self.dir / "events-2026-10.jsonl").write_text(line % drop + line % keep)
        m.prune(30, at=datetime(2026, 11, 30, tzinfo=timezone.utc))
        text = (self.dir / "events-2026-10.jsonl").read_text()
        self.assertIn(keep, text)
        self.assertNotIn(drop, text)

    def test_a_linked_worktree_has_the_same_repository_code_as_its_main_checkout(self):
        main = Path(self.tmp.name) / "main"
        (main / ".git" / "worktrees" / "wt1").mkdir(parents=True)
        (main / ".git" / "worktrees" / "wt1" / "commondir").write_text("../..\n")
        tree = Path(self.tmp.name) / "wt1"
        tree.mkdir()
        (tree / ".git").write_text("gitdir: %s\n" % (main / ".git" / "worktrees" / "wt1"))
        nested = tree / "nested"
        nested.mkdir()
        self.assertEqual(m.repo_code(tree), m.repo_code(main))
        self.assertEqual(m.repo_code(nested), m.repo_code(main))

    def test_first_edit_is_true_once_per_session(self):
        self.assertTrue(m.first_edit(SID))
        self.assertFalse(m.first_edit(SID))
        self.assertTrue(m.first_edit("sess-2"))

    def test_the_repository_code_follows_the_git_root_not_the_subfolder(self):
        sub = self.repo / "a" / "b"
        sub.mkdir(parents=True)
        self.assertEqual(m.repo_code(self.repo), m.repo_code(sub))
        other = Path(self.tmp.name) / "other"
        (other / ".git").mkdir(parents=True)
        self.assertNotEqual(m.repo_code(self.repo), m.repo_code(other))

    def test_invalid_consent_is_ignored(self):
        self.dir.mkdir()
        for text in ('{"date": "2026-11-03", "retention_days": 7}', "not json", "[]"):
            (self.dir / "consent.json").write_text(text)
            self.assertIsNone(m.read_consent())
        with self.assertRaises(ValueError):
            m.write_consent(7)

    def test_prune_drops_months_past_retention_and_old_markers(self):
        self.consent(30)
        for name in ("events-2026-07.jsonl", "events-2026-10.jsonl", "events-2026-11.jsonl", "notes.txt"):
            (self.dir / name).write_text("{}\n")
        m.first_edit("old")
        marker = self.dir / "markers" / "old"
        os.utime(marker, (0, 0))
        m.first_edit("fresh")
        m.prune(30, at=datetime(2026, 11, 3, tzinfo=timezone.utc))
        left = sorted(p.name for p in self.dir.iterdir() if p.is_file())
        self.assertEqual(left, ["consent.json", "events-2026-10.jsonl", "events-2026-11.jsonl", "notes.txt"])
        self.assertEqual(sorted(p.name for p in (self.dir / "markers").iterdir()), ["fresh"])

    def test_read_events_skips_bad_lines(self):
        self.consent()
        self.record()
        with open(next(self.dir.glob("events-*.jsonl")), "a") as handle:
            handle.write("garbage\n{\"event\": \"unknown\"}\n")
        events, skipped = m.read_events()
        self.assertEqual((len(events), skipped), (1, 2))

    def test_a_tampered_line_is_not_read_back(self):
        self.consent()
        self.record()
        good = json.loads(next(self.dir.glob("events-*.jsonl")).read_text().splitlines()[0])
        tampered = [{**good, "name": "</script><img src=x>"}, {**good, "extra": "x"}, {**good, "sid": "../x"},
                    {**good, "ts": "yesterday"}, {k: v for k, v in good.items() if k != "repo"}]
        with open(next(self.dir.glob("events-*.jsonl")), "a") as handle:
            handle.write("".join(json.dumps(line) + "\n" for line in tampered))
        events, skipped = m.read_events()
        self.assertEqual((len(events), skipped), (1, len(tampered)))

    def test_purge_removes_the_store_but_keeps_consent(self):
        self.consent()
        self.record()
        m.first_edit(SID)
        m.bump_errors()
        self.assertEqual(m.purge_store(), 3)
        self.assertIsNotNone(m.read_consent())
        self.assertEqual(m.read_events(), ([], 0))

    def test_a_damaged_or_oddly_named_event_file_does_not_stop_the_pruning(self):
        self.consent(30)
        (self.dir / "events-2026-10.jsonl").write_bytes(b"\xff\xfe not utf8\n")
        for name in ("events-2026-13.jsonl", "events-0000-01.jsonl", "events-2026-06.jsonl"):
            (self.dir / name).write_text("{}\n")
        m.first_edit("old")
        os.utime(self.dir / "markers" / "old", (0, 0))
        m.prune(30, at=datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertFalse((self.dir / "events-2026-06.jsonl").exists())
        self.assertFalse((self.dir / "markers" / "old").exists())
        self.assertEqual(m.read_events()[0], [])

    def test_an_impossible_date_or_a_trailing_newline_is_not_valid(self):
        self.consent()
        self.record()
        good = json.loads(next(self.dir.glob("events-*.jsonl")).read_text().splitlines()[0])
        self.assertTrue(m.valid_event(good))
        self.assertFalse(m.valid_event({**good, "ts": "2026-13-45T00:00:00.000+00:00"}))
        self.assertFalse(m.valid_event({**good, "ts": "2026-11-03T00:00:00Z"}))
        self.assertFalse(m.valid_id("abc\n"))
        self.assertIsNone(m.NAME.match("fnl-x\n"))
        self.assertFalse(m.valid_event({**good, "sid": "s1\n"}))

    def test_two_threads_creating_the_same_folder_both_succeed(self):
        import threading
        target = self.dir / "a" / "b"
        gate, errors = threading.Barrier(8), []

        def make():
            gate.wait()
            try:
                m.ensure_dir(target)
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=make) for _ in range(8)]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]
        self.assertEqual(errors, [])
        self.assertTrue(target.is_dir())

    def test_judge_privacy_and_spec_pin_the_exact_field_list(self):
        expected = {"site", "grader", "result", "followed"}
        for path in ("PRIVACY.md", "docs/specs/usage-metrics.md"):
            text = (ROOT / path).read_text()
            fields = re.search(r"Judge receipts hold only (.*?);", text).group(1)
            self.assertEqual(set(re.findall(r"`([^`]+)`", fields)), expected)
            self.assertIn("never hold a question, an answer, a cost, a file name or a path", text)
        spec = (ROOT / "docs/specs/usage-metrics.md").read_text()
        row = next(line for line in spec.splitlines() if line.startswith("| `judge` |"))
        self.assertEqual(set(re.findall(r"`([^`]+)` \(", row.split("|")[2])), expected)
        self.assertEqual(set(m.SCHEMA["judge"]), expected)

    def test_metrics_copy_list_covers_all_copies_and_ci(self):
        self.assertEqual(set(COPIES), set(ROOT.glob("skills/*/scripts/fnl_metrics.py")))
        ci = (ROOT / ".github/workflows/validate.yml").read_text()
        for path in [CORE, *COPIES]:
            self.assertIn(str(path.relative_to(ROOT)), ci)

    def test_shared_copies_equal_their_source(self):
        groups = [
            (CORE, COPIES),
            (ROOT / "skills/fnl-ask/references/plain-language.md",
             [ROOT / "skills/fnl-setup/references/plain-language.md"]),
        ]
        for source, copies in groups:
            for copy in copies:
                with self.subTest(copy=str(copy.relative_to(ROOT))):
                    self.assertTrue(copy.exists(), "missing copy")
                    self.assertEqual(copy.read_bytes(), source.read_bytes())

    def test_update_check_copy_equals_core(self):
        self.assertEqual((ROOT / "scripts/update_check.py").read_bytes(),
                         (ROOT / "skills/fnl-update/scripts/update_check.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
