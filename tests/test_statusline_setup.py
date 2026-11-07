"""Status-line setup accepts only explicit previews against synthetic settings."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import sys
import unittest
from unittest import mock

from tests.test_handover_state import setup_store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("statusline_setup", ROOT / "scripts" / "statusline_setup.py")
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


class StatuslineSetupTest(unittest.TestCase):
    def setUp(self):
        self.root = setup_store(self)
        self.home = self.root.parents[1]
        self.folder = self.home / ".claude"
        self.folder.mkdir(mode=0o700)
        self.target = self.folder / "settings.json"
        self.plan = self.root / "state" / "statusline" / "preview.json"
        patch = mock.patch.dict(os.environ, {}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["statusline_setup.py", *args]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sl.main()
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.cli("preview", *args)
        self.assertEqual((code, err), (0, ""))
        return out.split("Digest: ")[1].splitlines()[0]

    def apply(self, digest):
        code, out, err = self.cli("apply", "--digest", digest, "--yes")
        self.assertEqual((code, err), (0, ""))
        self.assertFalse(self.plan.exists())
        return out

    def refuse(self, *args):
        code, out, err = self.cli(*args)
        self.assertEqual(code, 1)
        self.assertEqual(len(err.splitlines()), 1)
        return out + err

    def test_preview_apply_remove_and_backup(self):
        before = b'{"other":true}\n'
        self.target.write_bytes(before)
        digest = self.preview()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        self.apply(digest)
        expected = {"other": True, "statusLine": sl.statusline()}
        self.assertEqual(json.loads(self.target.read_bytes()), expected)
        backup, = self.folder.glob("*.bak-*")
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.apply(self.preview("--remove"))
        self.assertEqual(json.loads(self.target.read_bytes()), {"other": True})
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(len(list(self.folder.glob("*.bak-*"))), 2)

    def test_missing_settings_created_then_removed(self):
        self.apply(self.preview())
        self.assertEqual(json.loads(self.target.read_bytes()), {"statusLine": sl.statusline()})
        self.apply(self.preview("--remove"))
        self.assertEqual(json.loads(self.target.read_bytes()), {})

    def test_existing_statusline_is_untouched_recipe_only_no_plan(self):
        for value in (None, "private" + "-command", {"type": "command", "command": "owned"}, sl.statusline()):
            self.target.write_text(json.dumps({"statusLine": value, "other": True}))
            before = self.target.read_bytes()
            code, out, err = self.cli("preview")
            self.assertEqual((code, err), (0, ""))
            self.assertIn("Recipe:", out)
            self.assertIn("record --host claude <", out)
            self.assertNotIn("--line", out)
            self.assertNotIn("Digest:", out)
            self.assertFalse(self.plan.exists())
            self.assertFalse(list(self.folder.glob("*.bak-*")))
            self.assertEqual(self.target.read_bytes(), before)
            self.assertNotIn("private" + "-command", out)

    def test_remove_never_removes_user_command(self):
        self.target.write_text(json.dumps({"statusLine": {"type": "command", "command": "owned"}}))
        before = self.target.read_bytes()
        self.refuse("preview", "--remove")
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(self.plan.exists())

    def test_yes_full_digest_expiry_and_mismatch_required(self):
        digest = self.preview()
        self.refuse("apply", "--digest", digest)
        self.refuse("apply", "--digest", digest[:12], "--yes")
        self.refuse("apply", "--digest", "0" * 64, "--yes")
        self.assertFalse(self.target.exists())
        with mock.patch.object(sl.time, "time", return_value=100000):
            expired = self.preview()
        self.refuse("apply", "--digest", expired, "--yes")
        self.assertFalse(self.target.exists())

    def test_changed_target_and_tampered_plan_refused(self):
        digest = self.preview()
        self.target.write_bytes(b'{"statusLine":"owned"}')
        before = self.target.read_bytes()
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(list(self.folder.glob("*.bak-*")))
        self.target.unlink()
        digest = self.preview()
        data = json.loads(self.plan.read_bytes())
        data["plan"]["remove"] = True
        self.plan.write_text(json.dumps(data))
        self.refuse("apply", "--digest", digest, "--yes")

    def test_private_plan_and_changed_data_root_refused(self):
        digest = self.preview()
        self.plan.chmod(0o644)
        self.refuse("apply", "--digest", digest, "--yes")
        self.plan.chmod(0o600)
        (self.root / "root.json").write_bytes(b"invalid")
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertFalse(self.target.exists())

    def test_unsafe_settings_folder_and_symlinks_refused(self):
        self.target.write_bytes(b"{}")
        for target, mode in ((self.target, 0o666), (self.folder, 0o777)):
            original = stat.S_IMODE(target.stat().st_mode)
            target.chmod(mode)
            self.refuse("preview")
            target.chmod(original)
        original = self.folder / "original"
        self.target.rename(original)
        self.target.symlink_to(original)
        self.refuse("preview")
        self.assertEqual(original.read_bytes(), b"{}")
        self.target.unlink()
        original.rename(self.target)
        alias = self.home / "alias"
        alias.symlink_to(self.folder, target_is_directory=True)
        self.refuse("preview", "--folder", str(alias))
        (self.home / ".git").write_text("gitdir: elsewhere")
        self.refuse("preview")

    def test_foreign_settings_owner_refused(self):
        self.target.write_bytes(b"{}")
        inode = self.target.stat().st_ino
        original = os.fstat
        def foreign(fd):
            info = original(fd)
            if info.st_ino == inode:
                fields = list(info)
                fields[4] = os.getuid() + 1
                return os.stat_result(fields)
            return info
        with mock.patch.object(os, "fstat", side_effect=foreign):
            self.refuse("preview")
        self.assertFalse(self.plan.exists())

    def test_multiple_folders_existing_line_prevents_all_writes(self):
        other = self.home / "other"
        other.mkdir(mode=0o700)
        target = other / "settings.json"
        target.write_text('{"statusLine":"owned"}')
        code, out, err = self.cli("preview", "--folder", str(self.folder), "--folder", str(other))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Recipe:", out)
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.target.exists())
        target.write_bytes(b"{}")
        digest = self.preview("--folder", str(self.folder), "--folder", str(other))
        target.write_bytes(b"invalid")
        self.refuse("apply", "--digest", digest, "--yes")
        self.assertFalse(self.target.exists())

    def test_invalid_deep_duplicate_and_nonfinite_json_refused_without_echo(self):
        for raw in (b"{bad", b"[]", b'{"statusLine":null,"statusLine":null}', b'{"x":NaN}', b'{"x":1e400}', b"[" * 1500):
            self.target.write_bytes(raw)
            self.refuse("preview")
            self.assertEqual(self.target.read_bytes(), raw)

    def test_command_quotes_plugin_path_and_rejects_moved_install(self):
        path = Path("/") / "synthetic install" / "plugin's scripts" / "context_snapshot.py"
        command = sl.statusline(path)["command"]
        self.assertTrue(command.startswith("python3 -I "))
        self.assertEqual(shlex.split(command), ["python3", "-I", str(path), "record", "--host", "claude", "--line"])
        digest = self.preview()
        with mock.patch.object(sl, "statusline", return_value={"type": "command", "command": "changed"}):
            self.refuse("apply", "--digest", digest, "--yes")
        self.assertFalse(self.target.exists())

    def test_new_shared_copies_match(self):
        for name in ("statusline_setup.py", "compact_setup.py"):
            self.assertEqual((ROOT / "scripts" / name).read_bytes(),
                             (ROOT / "skills" / "fnl-setup" / "scripts" / name).read_bytes())


class AntigravityStatuslineTest(unittest.TestCase):
    def setUp(self):
        StatuslineSetupTest.setUp(self)
        self.folder = self.home / ".gemini" / "antigravity-cli"
        self.folder.mkdir(parents=True, mode=0o700)
        self.target = self.folder / "settings.json"
        self.plugin = self.home / ".gemini" / "config" / "plugins" / "finolabs-vibecode"
        (self.plugin / "scripts").mkdir(parents=True)
        (self.plugin / ".git").mkdir()
        shutil.copyfile(ROOT / "scripts" / "context_snapshot.py", self.plugin / "scripts" / "context_snapshot.py")
        patch = mock.patch.object(sl, "__file__", str(self.plugin / "scripts" / "statusline_setup.py"))
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, action, *args):
        return StatuslineSetupTest.cli(self, action, "--host", "antigravity", *args)

    preview = StatuslineSetupTest.preview
    apply = StatuslineSetupTest.apply
    refuse = StatuslineSetupTest.refuse
    test_yes_full_digest_expiry_and_mismatch_required = StatuslineSetupTest.test_yes_full_digest_expiry_and_mismatch_required
    test_changed_target_and_tampered_plan_refused = StatuslineSetupTest.test_changed_target_and_tampered_plan_refused
    test_private_plan_and_changed_data_root_refused = StatuslineSetupTest.test_private_plan_and_changed_data_root_refused
    test_remove_never_removes_user_command = StatuslineSetupTest.test_remove_never_removes_user_command
    test_foreign_settings_owner_refused = StatuslineSetupTest.test_foreign_settings_owner_refused
    test_invalid_deep_duplicate_and_nonfinite_json_refused_without_echo = StatuslineSetupTest.test_invalid_deep_duplicate_and_nonfinite_json_refused_without_echo

    def test_preview_apply_remove_backup_and_preserves_other_json_values(self):
        before = b'{"allowRules":[{"tool":"example","allow":true}],"nested":{"number":1e2,"text":"\\u03bb"}}\n'
        self.target.write_bytes(before)
        original = json.loads(before)
        digest = self.preview()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        plan = json.loads(self.plan.read_bytes())["plan"]
        self.assertEqual(plan["host"], "antigravity")
        self.assertEqual(shlex.split(plan["statusLine"]["command"]),
                         ["python3", "-I", str(self.plugin / "scripts" / "context_snapshot.py"),
                          "record", "--host", "antigravity", "--line"])
        self.apply(digest)
        self.assertEqual(json.loads(self.target.read_bytes()), {**original, "statusLine": sl.statusline(host="antigravity")})
        backup, = self.folder.glob("*.bak-*")
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.apply(self.preview("--remove"))
        self.assertEqual(json.loads(self.target.read_bytes()), original)
        self.assertEqual(len(list(self.folder.glob("*.bak-*"))), 2)

    def test_missing_settings_and_existing_statusline_recipe_only(self):
        self.apply(self.preview())
        self.assertEqual(json.loads(self.target.read_bytes()), {"statusLine": sl.statusline(host="antigravity")})
        for value in (None, {}, "private" + "-command", sl.statusline(host="antigravity")):
            self.target.write_text(json.dumps({"statusLine": value}))
            before = self.target.read_bytes()
            code, out, err = self.cli("preview")
            self.assertEqual((code, err), (0, ""))
            self.assertIn("record --host antigravity <", out)
            self.assertNotIn("--line", out)
            self.assertNotIn("private" + "-command", out)
            self.assertNotIn("Digest:", out)
            self.assertFalse(self.plan.exists())
            self.assertEqual(self.target.read_bytes(), before)

    def test_no_folder_or_host_substitution_on_apply(self):
        self.refuse("preview", "--folder", str(self.folder))
        self.assertFalse(self.plan.exists())
        digest = self.preview()
        code, _, _ = StatuslineSetupTest.cli(self, "apply", "--digest", digest, "--yes")
        self.assertEqual(code, 1)
        self.assertFalse(self.target.exists())
        self.apply(digest)

    def test_fixed_target_revalidated_even_for_rehashed_private_plan(self):
        self.preview()
        saved = json.loads(self.plan.read_bytes())
        saved["plan"]["targets"][0]["path"] = str(self.home / ".claude" / "settings.json")
        saved["digest"] = sl.common.digest(saved["plan"])
        self.plan.write_text(json.dumps(saved))
        self.refuse("apply", "--digest", saved["digest"], "--yes")
        self.assertFalse(self.target.exists())
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    def test_self_contained_setup_copy_finds_whole_plugin_recorder(self):
        with mock.patch.object(sl, "__file__", str(self.plugin / "skills" / "fnl-setup" / "scripts" / "statusline_setup.py")):
            self.apply(self.preview())
        self.assertEqual(shlex.split(json.loads(self.target.read_bytes())["statusLine"]["command"])[2],
                         str(self.plugin / "scripts" / "context_snapshot.py"))

    def test_unsafe_target_folder_and_symlinks_refuse_preview_and_apply(self):
        self.target.write_bytes(b"{}")
        for target in (self.target, self.folder, self.plugin, self.plugin / "scripts"):
            for mode in (0o777, 0o775):
                digest = self.preview()
                original = stat.S_IMODE(target.stat().st_mode)
                target.chmod(mode)
                self.refuse("preview")
                self.refuse("apply", "--digest", digest, "--yes")
                self.assertEqual(self.target.read_bytes(), b"{}")
                target.chmod(original)
        for target in (self.target, self.folder, self.plugin, self.plugin / "scripts" / "context_snapshot.py"):
            digest = self.preview()
            other = target.with_name(target.name + "-original")
            target.rename(other)
            target.symlink_to(other, target_is_directory=other.is_dir())
            self.refuse("preview")
            self.refuse("apply", "--digest", digest, "--yes")
            target.unlink()
            other.rename(target)

    def test_development_checkout_ancestor_git_and_git_pointer_refused(self):
        other = self.home / "development-plugin"
        shutil.copytree(self.plugin, other)
        with mock.patch.object(sl, "__file__", str(other / "scripts" / "statusline_setup.py")):
            self.refuse("preview")
        for target in (self.home / ".gemini" / ".git", self.folder / ".git"):
            target.mkdir()
            self.refuse("preview")
            target.rmdir()
        (self.plugin / ".git").rmdir()
        (self.plugin / ".git").write_text("gitdir: " + "elsewhere")
        self.refuse("preview")


if __name__ == "__main__":
    unittest.main()
