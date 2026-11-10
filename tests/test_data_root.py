"""Data-root trust and relocation regressions using synthetic account homes."""

import importlib.util
import json
import os
import pwd
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_shared_copies import ci_copy_groups

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import data_root as dr
import fnl_metrics as fm


class DataRootTest(unittest.TestCase):
    def setUp(self):
        base = Path(pwd.getpwuid(os.getuid()).pw_dir) / "Library/Caches"
        if not base.is_dir():
            base = ROOT.parent
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        patcher = mock.patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(self.home)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.default = self.home / ".finolabs/vibecode"
        self.target = self.home / "moved"
        self.pointer = self.default / "root.json"
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "FNL_STATE_DIR": "",
            "XDG_STATE_HOME": "", "XDG_CONFIG_HOME": "", "ORCHESTRATION_HOST_CONFIG": ""})
        env.start()
        self.addCleanup(env.stop)

    def pointer_to(self, root=None, identity="test-root"):
        self.default.mkdir(parents=True, exist_ok=True)
        state = self.default / "state"
        state.mkdir(exist_ok=True)
        (state / "consent.json").write_text('{"retention_days":30,"date":"2026-01-01"}')
        self.target.mkdir(exist_ok=True, mode=0o700)
        (self.target / ".root-id").write_text("test-root")
        self.pointer.write_text(json.dumps({"root": str(root or self.target), "id": identity}))

    def invalid(self):
        self.assertEqual(dr.data_root(), (self.default, "invalid"))
        self.assertIsNone(dr.consent_root())
        self.assertIsNone(fm.read_consent())
        import mode
        self.assertEqual(mode.effective(keys=("auto_gate",)), {"auto_gate": "off"})
        with self.assertRaises((OSError, ValueError)):
            with dr.data_folder("state/quota", create=True):
                pass

    def test_default_without_pointer(self):
        self.assertEqual(dr.data_root(), (self.default, "default"))
        self.assertEqual(dr.consent_root(), self.default)

    def test_group_writable_home_without_pointer(self):
        self.home.chmod(0o775)
        self.assertEqual(dr.data_root(), (self.default, "default"))

    def test_valid_pointer(self):
        self.pointer_to()
        self.assertEqual(dr.data_root(), (self.target, "relocated"))

    def test_relative_pointer_root(self):
        self.pointer_to("relative")
        self.invalid()

    def test_symlink_pointer(self):
        self.pointer_to()
        saved = self.home / "saved"
        self.pointer.rename(saved)
        self.pointer.symlink_to(saved)
        self.invalid()

    def test_foreign_pointer(self):
        self.pointer_to()
        original = os.fstat
        inode = self.pointer.stat().st_ino
        def foreign(fd):
            value = original(fd)
            return SimpleNamespace(st_mode=value.st_mode, st_size=value.st_size,
                                   st_uid=os.getuid() + 1) if value.st_ino == inode else value
        with mock.patch.object(os, "fstat", side_effect=foreign):
            self.invalid()

    def test_oversized_pointer(self):
        self.pointer_to()
        self.pointer.write_bytes(b" " * 1025)
        self.invalid()

    def test_truncated_pointer(self):
        self.pointer_to()
        self.pointer.write_text('{"root":')
        self.invalid()

    def test_non_json_pointer(self):
        self.pointer_to()
        self.pointer.write_text("not json")
        self.invalid()

    def test_mismatched_id(self):
        self.pointer_to(identity="other")
        self.invalid()

    def test_symlink_root(self):
        self.pointer_to()
        other = self.home / "other"
        self.target.rename(other)
        self.target.symlink_to(other, target_is_directory=True)
        self.invalid()

    def test_group_writable_root(self):
        self.pointer_to()
        self.target.chmod(0o770)
        self.invalid()

    def test_root_inside_git_work_tree(self):
        self.pointer_to()
        (self.home / ".git").write_text("gitdir: ignored")
        self.invalid()

    def test_writable_ancestor(self):
        self.pointer_to()
        self.home.chmod(0o770)
        self.addCleanup(self.home.chmod, 0o700)
        self.invalid()

    def test_foreign_ancestor(self):
        self.pointer_to()
        original = os.fstat
        inode = self.home.parent.stat().st_ino
        def foreign(fd):
            value = original(fd)
            return SimpleNamespace(st_mode=value.st_mode, st_uid=os.getuid() + 1) if value.st_ino == inode else value
        with mock.patch.object(os, "fstat", side_effect=foreign):
            self.invalid()

    def test_environment_cannot_supply_consent(self):
        decoy = self.home / "decoy"
        decoy.mkdir()
        (decoy / "consent.json").write_text('{"retention_days":90,"date":"2026-01-01"}')
        with mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(decoy), "HOME": str(decoy),
                "XDG_STATE_HOME": str(decoy), "XDG_CONFIG_HOME": str(decoy),
                "ORCHESTRATION_HOST_CONFIG": str(decoy / "host.md")}):
            self.assertIsNone(fm.read_consent())
            self.assertEqual(dr.data_root(), (self.default, "default"))
            with dr.data_folder("state/quota", create=True) as folder:
                dr.atomic_write(folder, "marker", b"canonical")
        self.assertTrue((self.default / "state/quota/marker").exists())
        self.assertFalse((decoy / "marker").exists())

    def test_relocated_consent_and_opt_ins_ignore_old_folder(self):
        self.pointer_to()
        self.target.joinpath("host.md").write_text("## Auto gate\non\n## Routing\noff\n## Delegation mode\nauto\n## Route judgment\n- Instruction check: on\n")
        self.default.joinpath("host.md").write_text("## Auto gate\noff\n## Routing\non\n")
        import mode
        with mock.patch.dict(os.environ, {"ORCHESTRATION_HOST_CONFIG": str(self.default / "host.md")}, clear=True):
            self.assertEqual(mode.effective(keys=("auto_gate", "routing")), {"auto_gate": "on", "routing": "off"})
            fm.write_consent(90)
            self.assertIsNotNone(fm.read_consent())
            self.assertEqual(json.loads((self.default / "state/consent.json").read_text())["retention_days"], 30)
            self.target.joinpath("host.md").write_text("## Auto gate\noff\n")
            self.default.joinpath("host.md").write_text("## Auto gate\non\n")
            self.assertEqual(mode.effective(keys=("auto_gate",)), {"auto_gate": "off"})

    def test_invalid_pointer_does_not_reactivate_old_consent(self):
        fm.write_consent(90)
        self.pointer_to(identity="mismatch")
        self.invalid()

    def test_unsafe_consent_component(self):
        outside = self.home / "outside"
        outside.mkdir()
        outside.joinpath("consent.json").write_text('{"retention_days":90,"date":"2026-01-01"}')
        self.default.mkdir(parents=True)
        self.default.joinpath("state").symlink_to(outside, target_is_directory=True)
        self.assertIsNone(fm.read_consent())

    def location(self):
        spec = importlib.util.spec_from_file_location("data_location", ROOT / "skills/fnl-setup/scripts/data_location.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def seed_move(self):
        self.default.mkdir(parents=True)
        for name in ("host.md", "ledger.jsonl", "state/consent.json", "state/deep/item", "logs/run", "bin/tool", "tmp/skip"):
            path = self.default / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        (self.default / "state/link").symlink_to(self.default / "host.md")
        os.mkfifo(self.default / "state/pipe")
        self.default.joinpath("logs/link").symlink_to(self.default / "state", target_is_directory=True)

    def test_move_preview_digest_and_copy_without_deleting(self):
        self.seed_move()
        move = self.location()
        before = sorted(str(p) for p in self.home.rglob("*"))
        target, files, digest = move.preview(self.target)
        self.assertEqual(before, sorted(str(p) for p in self.home.rglob("*")))
        self.assertEqual(set(files), {"host.md", "ledger.jsonl", "state/consent.json", "state/deep/item", "logs/run", "bin/tool"})
        move.apply(target, digest, yes=True)
        self.assertEqual(dr.data_root(), (target, "relocated"))
        for name in files:
            self.assertEqual((target / name).read_bytes(), (self.default / name).read_bytes())
            self.assertEqual((target / name).stat().st_mode & 0o777, 0o600)
        for path in target.rglob("*"):
            if path.is_dir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        self.assertFalse((target / "tmp").exists())
        self.assertFalse((target / "state/link").exists())
        self.assertTrue((self.default / "tmp/skip").exists())

    def test_move_requires_yes_and_digest_without_writes(self):
        self.seed_move()
        move = self.location()
        _, _, expected = move.preview(self.target)
        for digest, yes in ((expected[:8], True), (expected[:63], True), (expected + "a", True), ("g" * 64, True), (None, True), ("a" * 8, True), ("bad", True), ("a" * 64, False)):
            with self.subTest(digest=digest, yes=yes), self.assertRaises(ValueError):
                move.apply(self.target, digest, yes)
            self.assertFalse(self.target.exists())
            self.assertFalse(self.pointer.exists())

    def test_digest_binds_target_and_contents(self):
        self.seed_move()
        move = self.location()
        _, _, digest = move.preview(self.target)
        with self.assertRaises(ValueError):
            move.apply(self.home / "different", digest, True)
        self.default.joinpath("host.md").write_text("changed")
        with self.assertRaises(ValueError):
            move.apply(self.target, digest, True)
        self.assertFalse(self.target.exists())

    def test_move_refuses_nonempty_target(self):
        self.seed_move()
        self.target.mkdir()
        (self.target / "existing").touch()
        with self.assertRaises(ValueError):
            self.location().preview(self.target)
        self.assertFalse(self.pointer.exists())

    def test_copy_change_never_publishes_pointer(self):
        self.seed_move()
        move = self.location()
        _, _, digest = move.preview(self.target)
        original = move.file_hash
        def change(folder, name, output=None):
            if output is not None:
                self.default.joinpath("host.md").write_text("changed during copy")
            return original(folder, name, output)
        with mock.patch.object(move, "file_hash", side_effect=change), self.assertRaises(ValueError):
            move.apply(self.target, digest, True)
        self.assertFalse(self.pointer.exists())

    def test_instruction_payload_uses_relocated_consent(self):
        self.pointer_to()
        self.default.joinpath("host.md").write_text("## Route judgment\n- Instruction check: on\n")
        self.target.joinpath("host.md").write_text("## Route judgment\n- Instruction check: off\n")
        spec = importlib.util.spec_from_file_location("root_checkup", ROOT / "skills/fnl-setup/scripts/checkup.py")
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        with mock.patch.object(check, "instruction_scan", return_value=({}, [], {})) as scan, mock.patch.object(
                check, "judge_payload", return_value="allowed"), mock.patch.dict(os.environ, {
                    "ORCHESTRATION_HOST_CONFIG": str(self.default / "host.md")}):
            self.assertEqual(check.collect(payload=True), "")
            scan.assert_not_called()
            self.target.joinpath("host.md").write_text("## Route judgment\n- Instruction check: on\n")
            self.assertEqual(check.collect(payload=True), "allowed")
            self.pointer.write_text("invalid")
            self.assertEqual(check.collect(payload=True), "")

    def test_gate_state_follows_relocation(self):
        self.pointer_to()
        import auto_gate
        with mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(self.default / "state"), "HOME": str(self.default)}):
            auto_gate.write_decision("a" * 12, "keep")
        self.assertTrue((self.target / "state/auto-gate" / ("a" * 12 + ".json")).is_file())
        self.assertFalse((self.default / "state/auto-gate").exists())

    def test_foreign_root(self):
        self.pointer_to()
        original = os.fstat
        inode = self.target.stat().st_ino
        def foreign(fd):
            value = original(fd)
            return SimpleNamespace(st_mode=value.st_mode, st_uid=os.getuid() + 1) if value.st_ino == inode else value
        with mock.patch.object(os, "fstat", side_effect=foreign):
            self.invalid()

    def test_missing_or_symlinked_root_id(self):
        self.pointer_to()
        marker = self.target / ".root-id"
        marker.unlink()
        self.invalid()
        outside = self.home / "identity"
        outside.write_text("test-root")
        marker.symlink_to(outside)
        self.invalid()

    def test_revoke_uses_canonical_consent_with_event_override(self):
        self.pointer_to()
        fm.write_consent(90)
        decoy = self.home / "events"
        decoy.mkdir()
        (decoy / "consent.json").write_text("keep decoy unchanged")
        spec = importlib.util.spec_from_file_location("root_refresh", ROOT / "skills/fnl-status/scripts/refresh.py")
        refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        with mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(decoy)}), mock.patch("builtins.print"):
            refresh.cmd_consent(SimpleNamespace(revoke=True, yes=True))
        self.assertIsNone(fm.read_consent())
        self.assertEqual((decoy / "consent.json").read_text(), "keep decoy unchanged")

    def test_invalid_root_consent_commands_exit_with_one_error_and_no_writes(self):
        self.pointer_to(identity="mismatch")
        spec = importlib.util.spec_from_file_location("root_refresh_invalid", ROOT / "skills/fnl-status/scripts/refresh.py")
        refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        before = {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        for revoke in (True, False):
            with self.subTest(revoke=revoke), mock.patch("builtins.print") as output:
                with self.assertRaises(SystemExit) as error:
                    refresh.cmd_consent(SimpleNamespace(revoke=revoke, retention=30, yes=True))
                self.assertEqual(str(error.exception), "consent: invalid data root; nothing recorded")
                output.assert_not_called()
            self.assertEqual(before, {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()})

    def test_revoke_without_state_is_idempotent(self):
        spec = importlib.util.spec_from_file_location("root_refresh_empty", ROOT / "skills/fnl-status/scripts/refresh.py")
        refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        with mock.patch("builtins.print"):
            refresh.cmd_consent(SimpleNamespace(revoke=True, yes=True))
            refresh.cmd_consent(SimpleNamespace(revoke=True, yes=True))
        self.assertFalse(self.default.exists())

    def test_move_makes_existing_empty_target_private(self):
        self.seed_move()
        self.target.mkdir(mode=0o755)
        self.target.chmod(0o755)
        move = self.location()
        _, _, digest = move.preview(self.target)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        move.apply(self.target, digest, True)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)

    def test_invalid_pointer_stops_update_network_and_worker(self):
        self.pointer_to(identity="mismatch")
        (self.default / "state/update-check.json").write_text('{"checked_at":0,"tag":"9.0.0"}')
        import update_check
        with mock.patch.object(update_check, "fetch") as fetch, mock.patch.object(
                update_check, "start_fetch") as spawn, mock.patch.dict(os.environ, {
                    "FNL_STATE_DIR": str(self.default / "state"), "FNL_UPDATE_CHECK": ""}):
            update_check.run(["--fetch"])
            update_check.run([])
            fetch.assert_not_called()
            spawn.assert_not_called()
            self.assertIsNone(update_check.cache())

    def test_invalid_pointer_denies_ledger_read_and_append(self):
        self.pointer_to(identity="mismatch")
        old = self.default / "ledger.jsonl"
        old.write_text("old ledger must not be read")
        spec = importlib.util.spec_from_file_location("root_ledger", ROOT / "skills/fnl-delegate/scripts/ledger.py")
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        with mock.patch.dict(os.environ, {"ORCHESTRATION_LEDGER": str(old), "HOME": str(self.default),
                                         "XDG_STATE_HOME": str(self.default)}):
            with self.assertRaises(ValueError):
                ledger.load()
            with self.assertRaises(ValueError):
                ledger.append({"event": "start"})
        self.assertEqual(old.read_text(), "old ledger must not be read")


COPIES = ["scripts/data_root.py",
          "skills/fnl-coding-router/scripts/data_root.py",
          "skills/fnl-delegate/scripts/data_root.py",
          "skills/fnl-review-gate/scripts/data_root.py",
          "skills/fnl-setup/scripts/data_root.py",
          "skills/fnl-status/scripts/data_root.py",
          "skills/fnl-session-hygiene/scripts/data_root.py",
          "skills/fnl-checks/scripts/data_root.py",
          "skills/fnl-restore-point/scripts/data_root.py", "skills/fnl-update/scripts/data_root.py"]


class DataRootCopiesTest(unittest.TestCase):
    def test_every_copy_is_identical_and_listed_in_ci(self):
        actual = {str(p.relative_to(ROOT)) for base in (ROOT / "scripts", ROOT / "skills") for p in base.rglob("data_root.py")}
        self.assertEqual(actual, set(COPIES))
        self.assertEqual(next(group for group in ci_copy_groups() if "scripts/data_root.py" in group), COPIES)
        for name in COPIES:
            self.assertEqual((ROOT / name).read_bytes(), (ROOT / COPIES[0]).read_bytes())

    def test_no_alternative_data_paths(self):
        import ast
        import re
        scripts = [*(ROOT / "scripts").glob("*.py"), *(ROOT / "skills").glob("*/scripts/*.py")]
        bad = []
        for path in scripts:
            if path.name == "data_root.py":
                continue
            source = path.read_text()
            allowed = set()
            if path.name == "fnl_metrics.py":
                # Events/dashboard compatibility only; temporary atomic files stay beside their destination.
                for node in ast.parse(source).body:
                    if isinstance(node, ast.FunctionDef) and node.name in {"state_dir", "atomic_write"}:
                        allowed.update(range(node.lineno, node.end_lineno + 1))
                    if isinstance(node, ast.Import) and any(a.name == "tempfile" for a in node.names):
                        allowed.add(node.lineno)
            for line, text in enumerate(source.splitlines(), 1):
                if re.search(r"\.finolabs/vibecode|FNL_STATE_DIR|\btempfile\b", text) and line not in allowed:
                    bad.append((str(path.relative_to(ROOT)), line))
        self.assertEqual(bad, [])
