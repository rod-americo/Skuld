from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import skuld_macos_sync as sync
from skuld_macos_model import ManagedService


class MacosSyncTest(unittest.TestCase):
    def test_sync_backfills_launchd_plist_metadata(self) -> None:
        saved = []
        service = ManagedService("worker", "/bin/worker", "Worker", display_name="worker")

        with tempfile.TemporaryDirectory() as tempdir:
            plist_path = Path(tempdir) / "worker.plist"
            plist_path.write_bytes(
                plistlib.dumps(
                    {
                        "WorkingDirectory": "/srv/worker",
                        "UserName": "rodrigo",
                        "StandardOutPath": "/tmp/skuld/worker/out.log",
                    }
                )
            )

            changed = sync.sync_registry_from_launchd(
                None,
                load_registry=lambda **kwargs: [service],
                save_registry=saved.append,
                plist_path_for_service=lambda service: plist_path,
            )

        self.assertEqual(changed, 1)
        [updated] = saved[0]
        self.assertEqual(updated.working_dir, "/srv/worker")
        self.assertEqual(updated.user, "rodrigo")
        self.assertEqual(updated.log_dir, "/tmp/skuld/worker")

    def test_sync_does_not_write_when_target_is_unchanged(self) -> None:
        saved = []
        service = ManagedService("worker", "/bin/worker", "Worker", display_name="worker")

        changed = sync.sync_registry_from_launchd(
            "worker",
            load_registry=lambda **kwargs: [service],
            save_registry=saved.append,
            plist_path_for_service=lambda service: Path("/tmp/missing.plist"),
        )

        self.assertEqual(changed, 0)
        self.assertEqual(saved, [])


if __name__ == "__main__":
    unittest.main()
