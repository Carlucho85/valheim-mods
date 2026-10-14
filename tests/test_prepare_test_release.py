import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_test_release


class TestReleasePreparationTests(unittest.TestCase):
    def test_snapshot_mod_is_staged_under_its_plugin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "base.zip"
            payload = b"AmmoCount 0.5.1"
            dependency_payload = b"Shared dependency"
            source_path = "BepInEx/plugins/thunderstore/AmmoCount.dll"
            with zipfile.ZipFile(snapshot, "w") as archive:
                archive.writestr(source_path, payload)
                archive.writestr(
                    "BepInEx/plugins/thunderstore/Zolantris.Shared.dll",
                    dependency_payload,
                )

            mod = {
                "owner": "aedenthorn",
                "name": "AmmoCount",
                "version": "0.5.1",
                "sourceSnapshot": source_path,
                "snapshotTarget": "AmmoCount.dll",
                "sourceSha256": hashlib.sha256(payload).hexdigest(),
                "sourceSnapshotFiles": [
                    {
                        "source": "BepInEx/plugins/thunderstore/Zolantris.Shared.dll",
                        "target": "Zolantris.Shared.dll",
                    }
                ],
            }
            cache = root / "downloads"
            cache.mkdir()
            with patch.object(prepare_test_release, "BASE_SERVER_SNAPSHOT", snapshot):
                data = prepare_test_release.fetch_mod(mod, cache)

            package_path = cache / "aedenthorn-AmmoCount-0.5.1.zip"
            self.assertEqual(data, package_path.read_bytes())
            self.assertEqual(mod["sourceSha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(
                prepare_test_release.runtime_files(mod, data, package_path),
                {
                    "AmmoCount.dll": payload,
                    "Zolantris.Shared.dll": dependency_payload,
                },
            )
            self.assertEqual(
                mod["sourceSnapshotFiles"][0]["sha256"],
                hashlib.sha256(dependency_payload).hexdigest(),
            )

    def test_snapshot_mod_rejects_paths_outside_the_plugin_tree(self) -> None:
        mod = {
            "owner": "aedenthorn",
            "name": "AmmoCount",
            "version": "0.5.1",
            "sourceSnapshot": "BepInEx/plugins/../config/secrets.cfg",
            "snapshotTarget": "AmmoCount.dll",
        }
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(prepare_test_release.TestReleaseError):
                prepare_test_release.fetch_mod(mod, Path(temporary))


if __name__ == "__main__":
    unittest.main()
