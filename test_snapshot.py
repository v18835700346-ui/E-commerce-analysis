"""Regression checks for preventing mixed simulation snapshots."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validate_data import verify_snapshot


class SnapshotTests(unittest.TestCase):
    def test_accepts_unchanged_and_rejects_modified_input(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "events.csv"
            sample.write_text("event_id\ne1\n", encoding="utf-8")
            manifest = {sample.name: hashlib.sha256(sample.read_bytes()).hexdigest()}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            verify_snapshot(root)
            sample.write_text("event_id\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Snapshot changed"):
                verify_snapshot(root)

    def test_missing_manifest_fails_closed(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                verify_snapshot(Path(directory))


if __name__ == "__main__":
    unittest.main()
