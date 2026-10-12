import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_client_pack


class ClientPackTests(unittest.TestCase):
    def make_archive(self, root: Path, entries: dict[str, bytes]) -> Path:
        path = root / "server-plugins.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return path

    def make_loader(self, root: Path) -> tuple[Path, str]:
        path = root / "loader.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "BepInExPack_Valheim/BepInEx/core/BepInEx.dll", b"loader"
            )
        digest = build_client_pack.sha256_file(path)
        return path, digest

    def test_safe_archive_paths_reject_traversal(self) -> None:
        for path in ("../escape.dll", "/root.dll", "C:/escape.dll", "plugins/../escape.dll"):
            with self.subTest(path=path), self.assertRaises(build_client_pack.PackageError):
                build_client_pack.safe_archive_path(path)

    def test_selects_unique_client_plugins_and_skips_server_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "plugins/QuickConnect/QuickConnect.dll": b"client",
                    "plugins/thunderstore/QuickConnect.dll": b"duplicate",
                    "plugins/thunderstore/ICONNX.png": b"keep",
                    "plugins/thunderstore/IconNX.png": b"skip duplicate artwork",
                    "plugins/MaxPlayerCount.dll": b"server only",
                    "plugins/thunderstore/quick_connect_servers.cfg": b"host:secret",
                    "plugins/vortex.deployment.json": b"local path",
                },
            )
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
            self.assertEqual(
                [output for _, output in selected],
                [
                    "BepInEx/plugins/QuickConnect/QuickConnect.dll",
                    "BepInEx/plugins/thunderstore/ICONNX.png",
                ],
            )

    def test_accepts_server_plugins_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = Path(temporary)
            plugins = server / "BepInEx" / "plugins"
            (plugins / "QuickConnect").mkdir(parents=True)
            (plugins / "QuickConnect" / "QuickConnect.dll").write_bytes(b"client")
            (plugins / "MaxPlayerCount.dll").write_bytes(b"server only")

            with build_client_pack.open_server_source(server) as source:
                selected = build_client_pack.discover_server_files(source)

            self.assertEqual(
                [output for _, output in selected],
                ["BepInEx/plugins/QuickConnect/QuickConnect.dll"],
            )

    def test_build_merges_localization_and_emits_integrity_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "plugins/AugaLite/AugaLite.dll": b"plugin",
                    "plugins/AugaLite/translations.json": json.dumps(
                        {"known": "English", "": ""}
                    ).encode(),
                    "plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json": json.dumps(
                        {"one": "Uno"}
                    ).encode(),
                    "plugins/XPortal/Translations/Spanish/xportal-translations-spanish.json": json.dumps(
                        {"greeting": "Hola"}
                    ).encode(),
                },
            )
            loader, loader_hash = self.make_loader(root)
            overrides = {
                "BepInEx/plugins/AugaLite/translations.json": json.dumps(
                    {"known": "Español", "": ""}
                ).encode(),
                "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json.overrides.json": json.dumps(
                    {"two": "Dos"}
                ).encode(),
                "BepInEx/plugins/XPortal/Translations/Spanish/xportal-translations-spanish.json.overrides.json": json.dumps(
                    {"portal": "Portal"}
                ).encode(),
            }
            original_overrides = build_client_pack.OVERRIDES
            try:
                override_dir = root / "overrides"
                for name, data in overrides.items():
                    target = override_dir / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                with patch.object(build_client_pack, "OVERRIDES", override_dir), patch.object(
                    build_client_pack,
                    "LOADER_INFO",
                    root / "bepinex-pack.json",
                ):
                    build_client_pack.LOADER_INFO.write_text(
                        json.dumps(
                            {
                                "version": "test",
                                "url": "not-used",
                                "sha256": loader_hash,
                                "archiveName": "BepInExPack_Valheim-test.zip",
                            }
                        ),
                        encoding="utf-8",
                    )
                    output_dir = root / "out"
                    manifest = build_client_pack.write_package(
                        source, output_dir, "v1.0.0", loader
                    )
                    server_directory = root / "server" / "BepInEx" / "plugins"
                    with zipfile.ZipFile(source) as server_archive:
                        for member in server_archive.infolist():
                            if member.is_dir() or not member.filename.startswith("plugins/"):
                                continue
                            target = server_directory / member.filename[len("plugins/") :]
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(server_archive.read(member))
                    directory_output = root / "directory-out"
                    directory_manifest = build_client_pack.write_package(
                        root / "server", directory_output, "v1.0.0", loader
                    )
            finally:
                build_client_pack.OVERRIDES = original_overrides

            self.assertEqual(manifest["version"], "v1.0.0")
            self.assertEqual(manifest["pluginDllCount"], 1)
            self.assertEqual(directory_manifest["fileCount"], manifest["fileCount"])
            with zipfile.ZipFile(directory_output / build_client_pack.PACKAGE_NAME) as package:
                self.assertIsNone(package.testzip())
            self.assertEqual(
                build_client_pack.sha256_file(output_dir / build_client_pack.PACKAGE_NAME),
                manifest["archiveSha256"],
            )
            with zipfile.ZipFile(output_dir / build_client_pack.PACKAGE_NAME) as package:
                backpack = json.loads(
                    package.read(
                        "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json"
                    )
                )
                self.assertEqual(backpack, {"one": "Uno", "two": "Dos"})
                auga = json.loads(
                    package.read("BepInEx/plugins/AugaLite/translations.json")
                )
                self.assertEqual(auga, {"known": "Español", "": ""})
                embedded = json.loads(
                    package.read(build_client_pack.PACKAGE_MANIFEST_NAME)
                )
                self.assertEqual(embedded["version"], "v1.0.0")
                self.assertTrue(all(item["sha256"] for item in embedded["files"]))


if __name__ == "__main__":
    unittest.main()
