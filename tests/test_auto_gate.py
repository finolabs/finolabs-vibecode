"""Auto gate state safety, with a synthetic account home only."""

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/auto_gate.py"


class AutoGateStateTest(unittest.TestCase):
    def test_helper_is_shipped(self):
        self.assertTrue(HELPER.is_file(), "shared auto gate helper is not implemented")

    def setUp(self):
        spec = importlib.util.spec_from_file_location("gate_test", HELPER)
        self.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gate)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.repo = self.home / "repo"
        self.repo.mkdir()
        (self.repo / ".git").touch()
        self.key = self.gate.repository_key(self.repo)
        patch = mock.patch.object(self.gate.pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(self.home)))
        patch.start()
        self.addCleanup(patch.stop)
        self.folder = self.home / ".finolabs/vibecode/state/auto-gate"
        self.path = self.folder / (self.key + ".json")

    def read(self):
        with self.gate.state_folder() as folder:
            return self.gate.read_state(folder, self.key)

    def test_repository_key_realpath_walk_and_no_git(self):
        nested = self.repo / "nested"
        nested.mkdir()
        link = self.home / "linked"
        link.symlink_to(nested, target_is_directory=True)
        self.assertEqual(self.gate.repository_key(link), hashlib.sha256(os.fsencode(self.repo)).hexdigest()[:12])
        self.assertIsNone(self.gate.repository_key(self.home))
        (nested / ".git").mkdir()
        self.assertNotEqual(self.gate.repository_key(nested), self.key)

    def test_decision_and_denied_merge_and_expiry(self):
        self.assertTrue(self.gate.claim_denial(self.key))
        denied = self.read()["denied"]
        self.gate.write_decision(self.key, "keep")
        self.assertEqual(self.read()["denied"], denied)
        self.assertEqual(self.read()["decision"], "keep")
        self.assertFalse(self.gate.claim_denial(self.key))
        old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
        self.path.write_text(json.dumps({"decision": "handoff", "decided": old, "denied": old}))
        self.assertTrue(self.gate.claim_denial(self.key))
        state = self.read()
        self.assertEqual(state["decision"], "handoff")
        self.assertEqual(state["decided"], old)
        self.assertNotEqual(state["denied"], old)
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_decoy_home_and_state_environment_ignored(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.repo), "FNL_STATE_DIR": str(self.repo),
                                          "XDG_STATE_HOME": str(self.repo)}):
            self.gate.write_decision(self.key, "handoff")
        self.assertTrue(self.path.is_file())
        self.assertFalse((self.repo / ".finolabs").exists())

    def test_exclusive_publish_loser_preserves_winner(self):
        with self.gate.state_folder() as folder:
            state = {"denied": datetime.now(timezone.utc).isoformat()}
            self.assertTrue(self.gate.write_state(folder, self.key, state, exclusive=True))
            self.assertFalse(self.gate.write_state(folder, self.key, {"denied": "other"}, exclusive=True))
            self.assertEqual(self.gate.read_state(folder, self.key), state)

    def test_unsafe_or_malformed_files_refused(self):
        with self.gate.state_folder():
            pass
        for data in (b"{", b"{}", b"[]", b"x" * 4097, b'{"decision":"other","decided":"bad"}',
                     b'{"denied":"bad"}', b'{"denied":"2026-01-01T00:00:00"}'):
            with self.subTest(data=data[:40]):
                self.path.write_bytes(data)
                with self.assertRaises((ValueError, TypeError)):
                    self.gate.claim_denial(self.key)
                self.assertEqual(self.path.read_bytes(), data)
        self.path.unlink()
        target = self.home / "target"
        target.write_text("{}")
        self.path.symlink_to(target)
        with self.assertRaises(OSError):
            self.gate.claim_denial(self.key)
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises(ValueError):
            self.gate.claim_denial(self.key)

    def test_symlinked_folder_refused(self):
        self.folder.parent.mkdir(parents=True)
        self.folder.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(OSError):
            self.gate.claim_denial(self.key)
        self.assertFalse((self.repo / (self.key + ".json")).exists())
