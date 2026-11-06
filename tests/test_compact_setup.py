"""Compaction writer acceptance; synthetic account and host files only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/fnl-setup/scripts/compact_setup.py"
spec = importlib.util.spec_from_file_location("compact_setup", SCRIPT)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


class CompactSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / "home")
        # Test-only seam: the system temporary ancestor (/tmp is sticky and
        # world-writable on Linux) would be refused; every check on the
        # synthetic tree itself stays in force.
        ancestors = {p.stat().st_ino for p in base.parents if p.stat().st_mode & 0o022}
        original = os.fstat

        def fstat(fd):
            info = original(fd)
            if info.st_ino in ancestors and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[0] &= ~0o022
                return os.stat_result(fields)
            return info
        patch = mock.patch.object(os, "fstat", side_effect=fstat)
        patch.start()
        self.addCleanup(patch.stop)
        self.claude = self.home / ".claude"
        self.codex = self.home / ".codex"
        self.claude.mkdir(mode=0o700)
        self.codex.mkdir(mode=0o700)
        self.target = self.claude / "settings.json"
        self.target.write_text('{"first": 1, "autoCompactWindow": 200000, "last": true}\n')
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "CODEX_HOME": str(self.codex)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.plan = self.home / ".finolabs/vibecode/state/compact/preview.json"

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(SCRIPT), *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cs.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def preview(self, host="claude", *extra):
        args = extra or ("--tokens", "150000")
        code, out, err = self.run_cli("preview", "--host", host, *args)
        self.assertEqual(code, 0, err)
        self.assertIn("Digest: ", out)
        return out.split("Digest: ")[1].splitlines()[0]

    def apply(self, digest):
        code, out, err = self.run_cli("apply", "--digest", digest, "--yes")
        self.assertEqual(code, 0, err)
        self.assertFalse(self.plan.exists())
        return out

    def refuse(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertNotEqual(code, 0)
        self.assertEqual(len(err.splitlines()), 1, err)
        return out + err

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def test_preview_changes_only_private_plan(self):
        before = self.snapshot()
        self.preview()
        after = self.snapshot()
        after.pop(str(self.plan.relative_to(self.home)))
        self.assertEqual(before, after)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)

    def test_claude_preserves_keys_order_and_backup_mode(self):
        before = self.target.read_bytes()
        self.target.chmod(0o640)
        self.apply(self.preview())
        self.assertEqual(self.target.read_text(), '{\n  "first": 1,\n  "autoCompactWindow": 150000,\n  "last": true\n}\n')
        backup, = self.claude.glob("settings.json.bak-*")
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o640)

    def test_backup_never_overwritten(self):
        self.apply(self.preview())
        backup, = self.claude.glob("*.bak-*")
        before = backup.read_bytes()
        self.apply(self.preview("claude", "--tokens", "180000"))
        self.assertEqual(backup.read_bytes(), before)
        self.assertTrue(Path(str(backup) + "-1").exists())

    def test_codex_insert_replace_remove_preserves_other_bytes(self):
        target = self.codex / "config.toml"
        original = b'# untouched\r\nmodel = "example"\r\n[features]\r\nflag = true\r\n'
        target.write_bytes(original)
        self.apply(self.preview("codex"))
        expected = original.replace(b'[features]', b'model_auto_compact_token_limit = 150000\r\n[features]')
        self.assertEqual(target.read_bytes(), expected)
        self.apply(self.preview("codex", "--tokens", "200000"))
        self.assertEqual(target.read_bytes(), expected.replace(b'150000', b'200000'))
        self.apply(self.preview("codex", "--off"))
        self.assertEqual(target.read_bytes(), original)

    def test_codex_no_table_and_missing_file(self):
        target = self.codex / "config.toml"
        self.apply(self.preview("codex"))
        self.assertEqual(target.read_bytes(), b'model_auto_compact_token_limit = 150000\n')
        target.write_bytes(b'model = "example"')
        self.apply(self.preview("codex"))
        self.assertEqual(target.read_bytes(), b'model = "example"\nmodel_auto_compact_token_limit = 150000\n')

    def test_codex_replacement_preserves_trailing_comment(self):
        target = self.codex / "config.toml"
        for parser in (cs.tomllib, None):
            for ending in (b"\n", b"\r\n", b""):
                with self.subTest(parser=parser, ending=ending), mock.patch.object(cs, "tomllib", parser):
                    original = b'# before\nmodel_auto_compact_token_limit = 200000 \t# keep # comment' + ending
                    target.write_bytes(original)
                    self.apply(self.preview("codex"))
                    self.assertEqual(target.read_bytes(), original.replace(b'200000', b'150000'))

    def test_off_and_no_difference(self):
        self.apply(self.preview("claude", "--off"))
        self.assertEqual(json.loads(self.target.read_bytes()), {"first": 1, "last": True})
        for host in ("claude", "codex"):
            before = self.snapshot()
            out = self.apply(self.preview(host, "--off"))
            self.assertIn("No difference.", out)
            self.assertEqual(before, self.snapshot())

    def test_same_value_does_not_rewrite_or_create_backup(self):
        cases = (("claude", self.target, b'{"autoCompactWindow":200000,"other":true}'),
                 ("codex", self.codex / "config.toml",
                  b'"model_auto_compact_token_limit"=200_000 \t# keep\r\n'))
        for host, target, raw in cases:
            with self.subTest(host=host):
                target.write_bytes(raw)
                before = self.snapshot()
                info = target.stat()
                code, out, err = self.run_cli("preview", "--host", host, "--tokens", "200000")
                self.assertEqual(code, 0, err)
                self.assertIn("No difference.", out)
                self.assertIn("(not needed)", out)
                digest = out.split("Digest: ")[1].splitlines()[0]
                with mock.patch.object(cs, "write_target", side_effect=AssertionError("unexpected write")):
                    self.assertIn("No difference.", self.apply(digest))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual((target.stat().st_ino, target.stat().st_mtime_ns),
                                 (info.st_ino, info.st_mtime_ns))

    def test_prefix_digest(self):
        digest = self.preview()
        before = self.snapshot()
        self.refuse("apply", "--digest", digest[:12], "--yes")
        self.assertEqual(before, self.snapshot())

    def test_missing_yes(self):
        digest = self.preview()
        before = self.snapshot()
        self.refuse("apply", "--digest", digest)
        self.assertEqual(before, self.snapshot())

    def test_expired_preview(self):
        with mock.patch("time.time", return_value=100000):
            digest = self.preview()
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertTrue(self.plan.exists())

    def test_edited_plan(self):
        digest = self.preview()
        saved = json.loads(self.plan.read_bytes())
        saved["plan"]["tokens"] = 250000
        self.plan.write_text(json.dumps(saved))
        self.refuse("apply", "--digest", digest, "--yes")

    def test_unreadable_plan(self):
        digest = self.preview()
        self.plan.unlink()
        self.plan.mkdir()
        self.refuse("apply", "--digest", digest, "--yes")

    def test_changed_target(self):
        digest = self.preview()
        self.target.write_text('{"changed":true}')
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertFalse(list(self.claude.glob("*.bak-*")))

    def test_symlink_target(self):
        original = self.claude / "original.json"
        self.target.rename(original)
        self.target.symlink_to(original)
        self.refuse("preview", "--host", "claude", "--tokens", "150000")

    def test_symlink_component(self):
        alias = self.home / "alias"
        alias.symlink_to(self.claude, target_is_directory=True)
        self.refuse("preview", "--host", "claude", "--folder", str(alias), "--tokens", "150000")

    def test_group_writable_folder(self):
        self.claude.chmod(0o770)
        self.refuse("preview", "--host", "claude", "--tokens", "150000")

    def test_git_work_tree(self):
        (self.home / ".git").write_text("gitdir: elsewhere")
        self.refuse("preview", "--host", "claude", "--tokens", "150000")

    def test_out_of_range_and_noninteger(self):
        for host, values in (("claude", (99999, 1000001, "1.5")), ("codex", (999, 10000001, "true"))):
            for value in values:
                with self.subTest(host=host, value=value):
                    self.refuse("preview", "--host", host, "--tokens", str(value))
        self.assertFalse(self.plan.exists())

    def test_invalid_json(self):
        self.target.write_text('{invalid private-content')
        out = self.refuse("preview", "--host", "claude", "--off")
        self.assertNotIn("private-content", out)
        self.assertFalse(self.plan.exists())

    def test_nonobject_json(self):
        self.target.write_text('["private-content"]')
        self.refuse("preview", "--host", "claude", "--off")
        self.assertFalse(self.plan.exists())

    def test_antigravity(self):
        before = self.snapshot()
        out = self.refuse("preview", "--host", "antigravity", "--off")
        self.assertIn("no documented setting; /compact only", out)
        self.assertEqual(before, self.snapshot())

    def test_environment_names_only(self):
        names = ("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "DISABLE_AUTO_COMPACT")
        with mock.patch.dict(os.environ, dict.fromkeys(names, "private-env-value")):
            code, out, err = self.run_cli("preview", "--host", "claude", "--tokens", "150000")
        self.assertEqual(code, 0, err)
        for name in names:
            self.assertIn(name, out)
        self.assertNotIn("private-env-value", out)
        self.assertNotIn('"first"', out)
        self.assertIn("sessions started afterwards", out)

    def test_claude_per_model_override_warns_without_exposing_contents(self):
        warning = "Warning: modelSettings contains a per-model autoCompactWindow that overrides the top-level setting."
        for tokens in (("--tokens", "150000"), ("--tokens", "200000"), ("--off",)):
            with self.subTest(tokens=tokens):
                models = {"other-model": {"other": True},
                          "private-model": {"autoCompactWindow": "private-value", "other": True},
                          "another-model": {"autoCompactWindow": 987654}}
                self.target.write_text(json.dumps({"autoCompactWindow": 200000, "modelSettings": models}))
                before = self.target.read_bytes()
                code, out, err = self.run_cli("preview", "--host", "claude", *tokens)
                self.assertEqual(code, 0, err)
                self.assertIn(warning, out)
                self.assertEqual(self.target.read_bytes(), before)
                digest = out.split("Digest: ")[1].splitlines()[0]
                applied = self.apply(digest)
                self.assertIn(warning, applied)
                for output in (out, applied):
                    self.assertNotIn("private-model", output)
                    self.assertNotIn("private-value", output)
                    self.assertNotIn("987654", output)
                expected = {"modelSettings": models}
                if tokens[0] == "--tokens":
                    expected["autoCompactWindow"] = int(tokens[1])
                self.assertEqual(json.loads(self.target.read_bytes()), expected)

    def test_claude_only_per_model_threshold_keys_warn(self):
        for models in (None, [], "private-value", {"private-model": None},
                       {"private-model": {"other": {"autoCompactWindow": 123456}}}):
            with self.subTest(models=models):
                self.target.write_text(json.dumps({"modelSettings": models}))
                code, out, err = self.run_cli("preview", "--host", "claude", "--tokens", "150000")
                self.assertEqual(code, 0, err)
                self.assertNotIn("Warning:", out)

    def test_multiple_folders_preflight_all_before_writing(self):
        extra = self.home / "extra"
        extra.mkdir(mode=0o700)
        other = extra / "settings.json"
        other.write_text('{}')
        digest = self.preview("claude", "--folder", str(self.claude), "--folder", str(extra), "--tokens", "150000")
        other.write_text('[]')
        before = self.snapshot()
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertEqual(before, self.snapshot())

    def test_codex_multiline_strings_and_table_keys_untouched(self):
        target = self.codex / "config.toml"
        original = b'note = """\n[not_a_table]\nmodel_auto_compact_token_limit = 77\n"""\n[real]\nmodel_auto_compact_token_limit = 88\n'
        target.write_bytes(original)
        self.apply(self.preview("codex"))
        self.assertEqual(target.read_bytes(), original.replace(b'[real]', b'model_auto_compact_token_limit = 150000\n[real]'))

    def test_codex_invalid_toml(self):
        (self.codex / "config.toml").write_text('model = [private-content')
        self.refuse("preview", "--host", "codex", "--tokens", "150000")

    def test_json_duplicate_and_nonfinite_values_refused(self):
        for raw in ('{"other": 1e400}', '{"other": NaN}', '{"other": 1, "other": 2}'):
            with self.subTest(raw=raw):
                self.target.write_text(raw)
                self.refuse("preview", "--host", "claude", "--tokens", "150000")
                self.assertEqual(self.target.read_text(), raw)

    def test_deep_json_and_plan_refused_on_one_line(self):
        self.target.write_text('[' * 1500 + '0' + ']' * 1500)
        self.refuse("preview", "--host", "claude", "--tokens", "150000")
        self.target.write_text('{}')
        digest = self.preview()
        self.plan.write_text('[' * 1500 + '0' + ']' * 1500)
        self.refuse("apply", "--digest", digest, "--yes")

    def test_codex_integer_literals_without_tomllib(self):
        target = self.codex / "config.toml"
        with mock.patch.object(cs, "tomllib", None):
            for literal in ("0x30d40", "0o606500", "0b110000110101000000", "200_000"):
                with self.subTest(literal=literal):
                    target.write_text('model_auto_compact_token_limit = ' + literal + '\n[features]\nflag = true\n')
                    self.apply(self.preview("codex"))
                    self.assertEqual(target.read_text(), 'model_auto_compact_token_limit = 150000\n[features]\nflag = true\n')
            target.write_text('model_auto_compact_token_limit = 0x30d40\n')
            self.apply(self.preview("codex", "--off"))
            self.assertEqual(target.read_bytes(), b'')
            code, out, err = self.run_cli("preview", "--host", "codex", "--off")
            self.assertEqual(code, 0, err)
            self.assertIn("TOML parse check skipped", out)
            target.write_text('model_auto_compact_token_limit = "private-content"\n')
            self.refuse("preview", "--host", "codex", "--tokens", "150000")

    def test_target_permissions_and_wrong_owner(self):
        self.target.chmod(0o660)
        self.refuse("preview", "--host", "claude", "--tokens", "150000")
        self.target.chmod(0o600)
        real_fstat = os.fstat
        def foreign_file(fd):
            info = real_fstat(fd)
            if stat.S_ISREG(info.st_mode):
                values = list(info)
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return info
        with mock.patch.object(os, "fstat", side_effect=foreign_file):
            self.refuse("preview", "--host", "claude", "--tokens", "150000")

    def test_symlink_replacement_after_preview(self):
        digest = self.preview()
        original = self.claude / "original.json"
        self.target.rename(original)
        self.target.symlink_to(original)
        before = original.read_bytes()
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertEqual(original.read_bytes(), before)
        self.assertFalse(list(self.claude.glob("*.bak-*")))

    def test_toml_fallback_refuses_ambiguous_key_forms(self):
        target = self.codex / "config.toml"
        forms = ('"\\u006dodel_auto_compact_token_limit" = 200000\n',
                 'model_auto_compact_token_limit.child = 1\n',
                 '[other]\nx = 1\n[model_auto_compact_token_limit]\ny = 2\n')
        with mock.patch.object(cs, "tomllib", None):
            for raw in forms:
                with self.subTest(raw=raw):
                    target.write_text(raw)
                    self.refuse("preview", "--host", "codex", "--tokens", "150000")
                    self.assertEqual(target.read_text(), raw)

    def test_nonprivate_plan_refused(self):
        digest = self.preview()
        self.plan.chmod(0o644)
        self.refuse("apply", "--digest", digest, "--yes")


if __name__ == "__main__":
    unittest.main()
