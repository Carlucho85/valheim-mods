import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_test_release


class StableClientBaseTests(unittest.TestCase):
    def test_stages_client_plugins_but_not_akh_bundle_or_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "client.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("BepInEx/plugins/Shared/Shared.dll", b"shared")
                archive.writestr(
                    "BepInEx/plugins/AKHPlugins/AKH_MasterKeybind.dll",
                    b"managed separately",
                )
                archive.writestr("README.txt", b"documentation")
            destination = root / "stage"

            count = prepare_test_release.stage_base_client_plugins(
                archive_path, destination
            )

            self.assertEqual(count, 1)
            self.assertEqual(
                (destination / "BepInEx" / "plugins" / "Shared" / "Shared.dll").read_bytes(),
                b"shared",
            )
            self.assertFalse(
                (destination / "BepInEx" / "plugins" / "AKHPlugins").exists()
            )

    def test_rejects_unsafe_base_client_archive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "client.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("BepInEx/plugins/Shared/Shared.dll", b"shared")
                archive.writestr("BepInEx/plugins/../../escape.dll", b"unsafe")

            with self.assertRaisesRegex(
                prepare_test_release.TestReleaseError, "Unsafe path"
            ):
                prepare_test_release.stage_base_client_plugins(
                    archive_path, root / "stage"
                )
