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

    def test_filters_quick_connect_and_server_only_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "plugins/QuickConnect/QuickConnect.dll": b"server-only",
                    "plugins/thunderstore/QuickConnect.dll": b"client",
                    "plugins/thunderstore/ICONNX.png": b"keep",
                    "plugins/thunderstore/IconNX.png": b"skip duplicate artwork",
                    "plugins/MaxPlayerCount.dll": b"server plugin",
                    "plugins/Other.dll": b"client plugin",
                    "plugins/thunderstore/quick_connect_servers.cfg": b"host:secret",
                    "plugins/vortex.deployment.json": b"local path",
                },
            )
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
                self.assertCountEqual(
                    [output for _, output in selected],
                    {
                        "BepInEx/plugins/Other.dll",
                        "BepInEx/plugins/thunderstore/ICONNX.png",
                    },
                )

    def test_prefers_direct_plugin_dll_over_thunderstore_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "plugins/QuickConnect/QuickConnect.dll": b"server version",
                    "plugins/thunderstore/QuickConnect.dll": b"different version",
                    "plugins/Other/Other.dll": b"direct plugin version",
                    "plugins/thunderstore/Other.dll": b"different package copy",
                },
            )
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
                self.assertCountEqual(
                    [output for _, output in selected],
                    ["BepInEx/plugins/Other/Other.dll"],
                )
                self.assertEqual(
                    archive.read(selected[0][0]),
                    b"direct plugin version",
                )

    def test_prefers_active_adventure_backpacks_thunderstore_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "BepInEx/plugins/AdventureBackpacks/AdventureBackpacks.dll": b"2.2.11",
                    "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json": b'{"stale":"old"}',
                    "BepInEx/plugins/thunderstore/AdventureBackpacks.dll": b"2.3.4",
                    "BepInEx/plugins/thunderstore/AdventureBackpacks.Spanish.json": b'{"active":"new"}',
                    "BepInEx/plugins/Other/Other.dll": b"other plugin",
                },
            )
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
                selected_files = {
                    output: archive.read(member) for member, output in selected
                }

            self.assertEqual(
                selected_files,
                {
                    "BepInEx/plugins/thunderstore/AdventureBackpacks.dll": b"2.3.4",
                    "BepInEx/plugins/thunderstore/AdventureBackpacks.Spanish.json": b'{"active":"new"}',
                    "BepInEx/plugins/Other/Other.dll": b"other plugin",
                },
            )

    def test_prefers_server_active_thunderstore_plugin_versions(self) -> None:
        stale_dlls = {
            "AmmoCount.dll",
            "BepInEx.ConfigDrawers.dll",
            "DoorOpenerBruh.dll",
            "MinimalStatusEffects.dll",
            "Advize_PlantEasily.dll",
            "ShieldMeBruh.dll",
        }
        entries = {}
        expected = {}
        for name in sorted(stale_dlls):
            entries[f"BepInEx/plugins/{name.removesuffix('.dll')}/{name}"] = (
                f"old-{name}".encode()
            )
            entries[f"BepInEx/plugins/thunderstore/{name}"] = (
                f"active-{name}".encode()
            )
            expected[f"BepInEx/plugins/thunderstore/{name}"] = (
                f"active-{name}".encode()
            )

        with tempfile.TemporaryDirectory() as temporary:
            source = self.make_archive(Path(temporary), entries)
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
                selected_files = {
                    output: archive.read(member) for member, output in selected
                }

        self.assertEqual(selected_files, expected)

    def test_accepts_server_plugins_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = Path(temporary)
            plugins = server / "BepInEx" / "plugins" / "Other"
            plugins.mkdir(parents=True)
            (plugins / "Other.dll").write_bytes(b"client")
            (plugins / "MaxPlayerCount.dll").write_bytes(b"server only")

            with build_client_pack.open_server_source(server) as source:
                selected = build_client_pack.discover_server_files(source)

            self.assertEqual(
                [output for _, output in selected],
                ["BepInEx/plugins/Other/Other.dll"],
            )

    def test_quick_connect_plugin_and_credentials_are_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root,
                {
                    "plugins/QuickConnect.dll": b"plugin",
                    "plugins/QuickConnect/quick_connect_servers.cfg": b"password",
                    "plugins/Other/Other.dll": b"client",
                },
            )
            with zipfile.ZipFile(source) as archive:
                selected = build_client_pack.discover_server_files(archive)
            self.assertCountEqual(
                [output for _, output in selected],
                [
                    "BepInEx/plugins/Other/Other.dll",
                ],
            )

    def test_rejects_quick_connect_client_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            override = root / "overrides" / "BepInEx" / "plugins" / "QuickConnect"
            override.mkdir(parents=True)
            (override / "QuickConnect.dll").write_bytes(b"plugin")
            with patch.object(build_client_pack, "OVERRIDES", root / "overrides"):
                with self.assertRaisesRegex(
                    build_client_pack.PackageError,
                    "Quick Connect cannot be included",
                ):
                    build_client_pack.load_overrides()

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
                    "plugins/MaxPlayerCount.dll": b"server plugin",
                    "plugins/QuickConnect/QuickConnect.dll": b"quick connect plugin",
                    "plugins/QuickConnect/quick_connect_servers.cfg": b"host:secret",
                    "BepInEx/plugins/AdventureBackpacks/AdventureBackpacks.dll": b"2.3.4",
                    "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json": json.dumps(
                        {"one": "Uno", "new": "Nueva"}
                    ).encode(),
                    "plugins/XPortal/Translations/Spanish/xportal-translations-spanish.json": json.dumps(
                        {"greeting": "Hola"}
                    ).encode(),
                },
            )
            loader, loader_hash = self.make_loader(root)
            plugin_overrides = root / "plugin-overrides" / "AugaLite"
            plugin_overrides.mkdir(parents=True)
            (plugin_overrides / "AugaLite.dll").write_bytes(b"updated plugin")
            overrides = {
                "BepInEx/plugins/AugaLite/translations.json": json.dumps(
                    {"known": "Español", "": ""}
                ).encode(),
                "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json.overrides.json": json.dumps(
                    {"one": "Mochila"}
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
                        source,
                        output_dir,
                        "v1.0.0",
                        loader,
                        plugin_override_dir=root / "plugin-overrides",
                    )
                    server_directory = root / "server" / "BepInEx" / "plugins"
                    with zipfile.ZipFile(source) as server_archive:
                        for member in server_archive.infolist():
                            relative = build_client_pack.plugin_relative_path(member.filename)
                            if member.is_dir() or relative is None:
                                continue
                            target = server_directory / relative
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(server_archive.read(member))
                    directory_output = root / "directory-out"
                    directory_manifest = build_client_pack.write_package(
                        root / "server", directory_output, "v1.0.0", loader
                    )
            finally:
                build_client_pack.OVERRIDES = original_overrides

            self.assertEqual(manifest["version"], "v1.0.0")
            self.assertEqual(manifest["pluginDllCount"], 3)
            self.assertEqual(directory_manifest["fileCount"], manifest["fileCount"])
            with zipfile.ZipFile(directory_output / build_client_pack.PACKAGE_NAME) as package:
                self.assertIsNone(package.testzip())
            self.assertEqual(
                build_client_pack.sha256_file(output_dir / build_client_pack.PACKAGE_NAME),
                manifest["archiveSha256"],
            )
            with zipfile.ZipFile(output_dir / build_client_pack.PACKAGE_NAME) as package:
                self.assertIn("BepInEx/plugins/AKHPlugins/manifest.json", package.namelist())
                akh_manifest = json.loads(
                    package.read("BepInEx/plugins/AKHPlugins/manifest.json")
                )
                self.assertEqual(akh_manifest["name"], "AKH Plugins")
                self.assertTrue(akh_manifest["private"])
                self.assertTrue(
                    any(
                        entry["target"]
                        == "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json"
                        and entry["mode"] == "merge-json"
                        for entry in akh_manifest["files"]
                    )
                )
                self.assertIn(
                    "BepInEx/plugins/AKHPlugins/customizations/BepInEx/plugins/AugaLite/translations.json",
                    package.namelist(),
                )
                backpack = json.loads(
                    package.read(
                        "BepInEx/plugins/AdventureBackpacks/Translations/AdventureBackpacks.Spanish.json"
                    )
                )
                self.assertEqual(backpack, {"one": "Mochila", "new": "Nueva"})
                auga = json.loads(
                    package.read("BepInEx/plugins/AugaLite/translations.json")
                )
                self.assertEqual(auga, {"known": "Español", "": ""})
                self.assertEqual(
                    package.read("BepInEx/plugins/AugaLite/AugaLite.dll"),
                    b"updated plugin",
                )
                self.assertNotIn("BepInEx/plugins/MaxPlayerCount.dll", package.namelist())
                self.assertEqual(
                    package.read("BepInEx/plugins/AdventureBackpacks/AdventureBackpacks.dll"),
                    b"2.3.4",
                )
                self.assertNotIn("BepInEx/plugins/thunderstore/AdventureBackpacks.dll", package.namelist())
                self.assertNotIn(
                    "BepInEx/plugins/QuickConnect/QuickConnect.dll",
                    package.namelist(),
                )
                self.assertNotIn(
                    "BepInEx/plugins/QuickConnect/quick_connect_servers.cfg",
                    package.namelist(),
                )
                embedded = json.loads(
                    package.read(build_client_pack.PACKAGE_MANIFEST_NAME)
                )
                self.assertEqual(embedded["version"], "v1.0.0")
                self.assertTrue(all(item["sha256"] for item in embedded["files"]))

    def test_packages_only_allowlisted_server_config_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = self.make_archive(root, {"plugins/Other/Other.dll": b"plugin"})
            config_folder = root / "config"
            config_folder.mkdir()
            (config_folder / "Other.cfg").write_bytes(b"Feature = true\n")
            (config_folder / "QuickConnect.cfg").write_text("Password = hidden\n", encoding="utf-8")
            allowlist = root / "allowlist.txt"
            allowlist.write_text("# reviewed configs\nOther.cfg\n", encoding="utf-8")
            loader, loader_hash = self.make_loader(root)
            loader_info = root / "bepinex-pack.json"
            loader_info.write_text(
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
            empty_overrides = root / "overrides"
            empty_overrides.mkdir()
            output_dir = root / "out"

            with patch.object(build_client_pack, "OVERRIDES", empty_overrides), patch.object(
                build_client_pack, "LOADER_INFO", loader_info
            ):
                manifest = build_client_pack.write_package(
                    server,
                    output_dir,
                    "v1.0.0",
                    loader,
                    config_folder,
                    allowlist,
                )

            with zipfile.ZipFile(output_dir / build_client_pack.PACKAGE_NAME) as package:
                self.assertEqual(package.read("BepInEx/config/Other.cfg"), b"Feature = true\n")
                self.assertNotIn("BepInEx/config/QuickConnect.cfg", package.namelist())
            with zipfile.ZipFile(output_dir / build_client_pack.PACKAGE_NAME) as package:
                embedded = json.loads(package.read(build_client_pack.PACKAGE_MANIFEST_NAME))
            self.assertTrue(
                any(item["path"] == "BepInEx/config/Other.cfg" for item in embedded["files"])
            )

    def test_rejects_sensitive_quick_connect_config_allowlist_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowlist = root / "allowlist.txt"
            allowlist.write_text("QuickConnect/quick_connect_servers.cfg\n", encoding="utf-8")
            with self.assertRaisesRegex(build_client_pack.PackageError, "Sensitive server config"):
                build_client_pack.load_server_configs(root, allowlist)

    def test_omits_quick_connect_plugin_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "QuickConnect").mkdir()
            (root / "QuickConnect" / "QuickConnect.dll").write_bytes(b"plugin")
            (root / "QuickConnect" / "quick_connect_servers.cfg").write_bytes(b"secret")
            overrides = build_client_pack.load_plugin_overrides(root)
            self.assertEqual(overrides, {})

    def test_rejects_sensitive_files_in_akh_plugins_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = root / "QuickConnect" / "quick_connect_servers.cfg"
            secret.parent.mkdir(parents=True)
            secret.write_text("password=redacted", encoding="utf-8")
            with patch.object(build_client_pack, "OVERRIDES", root):
                with self.assertRaisesRegex(
                    build_client_pack.PackageError,
                    "Sensitive or server-only file",
                ):
                    build_client_pack.load_akh_plugin_bundle()

    def test_akh_plugins_contains_menu_customization_and_translations(self) -> None:
        metadata, customizations, runtime = build_client_pack.load_akh_plugin_bundle()
        self.assertEqual(metadata["name"], "AKH Plugins")
        self.assertIn("BepInEx/config/ValheimMenu/ValheimMenu.cfg", customizations)
        self.assertIn("BepInEx/config/ValheimMenu/logo.png", customizations)
        self.assertIn("BepInEx/plugins/AugaLite/translations.json", customizations)
        self.assertIn("BepInEx/config/ishid4.mods.betterarchery.cfg", customizations)
        self.assertIn(
            "BepInEx/config/randyknapp.mods.equipmentandquickslots.cfg",
            customizations,
        )
        self.assertNotIn("BepInEx/config/akh.masterkeybind.cfg", customizations)
        self.assertEqual(
            runtime["AKH_MasterKeybind.dll"],
            (build_client_pack.AKH_PLUGIN_RUNTIME / "AKH_MasterKeybind.dll").read_bytes(),
        )
        self.assertTrue(
            customizations["BepInEx/config/ValheimMenu/logo.png"].startswith(b"\x89PNG\r\n\x1a\n")
        )
        self.assertIn(
            "Title = Akai Hoshi: Changarök".encode(),
            customizations["BepInEx/config/ValheimMenu/ValheimMenu.cfg"],
        )

    def test_packages_shared_hud_configs_but_not_personal_keybind_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(root, {"plugins/Other/Other.dll": b"plugin"})
            loader, loader_hash = self.make_loader(root)
            with patch.object(build_client_pack, "LOADER_INFO", root / "bepinex-pack.json"):
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
                output = root / "out"
                build_client_pack.write_package(source, output, "v1.2.0", loader)

            with zipfile.ZipFile(output / build_client_pack.PACKAGE_NAME) as package:
                names = set(package.namelist())
                self.assertIn("BepInEx/config/ishid4.mods.betterarchery.cfg", names)
                self.assertIn(
                    "BepInEx/config/randyknapp.mods.equipmentandquickslots.cfg",
                    names,
                )
                self.assertNotIn("BepInEx/config/akh.masterkeybind.cfg", names)

    def test_akh_runtime_files_are_packaged_as_own_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_archive(
                root, {"plugins/Other/Other.dll": b"plugin"}
            )
            loader, loader_hash = self.make_loader(root)
            loader_info = root / "bepinex-pack.json"
            loader_info.write_text(
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
            manifest_path = root / "akh-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "name": "AKH Plugins",
                        "version": "1.1.0",
                        "private": True,
                    }
                ),
                encoding="utf-8",
            )
            customizations = root / "customizations"
            customizations.mkdir()
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "AKHPlugins.dll").write_bytes(b"private plugin")
            with (
                patch.object(build_client_pack, "AKH_PLUGIN_RUNTIME", runtime),
                patch.object(build_client_pack, "AKH_PLUGIN_MANIFEST", manifest_path),
                patch.object(build_client_pack, "OVERRIDES", customizations),
                patch.object(build_client_pack, "LOADER_INFO", loader_info),
            ):
                output = root / "out"
                build_client_pack.write_package(
                    source, output, "v1.2.3-beta.1", loader
                )
            with zipfile.ZipFile(output / build_client_pack.PACKAGE_NAME) as package:
                self.assertEqual(
                    package.read(
                        "BepInEx/plugins/AKHPlugins/AKHPlugins.dll"
                    ),
                    b"private plugin",
                )
                generated_manifest = json.loads(
                    package.read("BepInEx/plugins/AKHPlugins/manifest.json")
                )
                self.assertEqual(generated_manifest["version"], "1.2.3-beta.1")
                self.assertEqual(
                    generated_manifest["files"],
                    [
                        {
                            "source": "runtime/AKHPlugins.dll",
                            "target": "BepInEx/plugins/AKHPlugins/AKHPlugins.dll",
                            "mode": "install",
                        }
                    ],
                )


if __name__ == "__main__":
    unittest.main()
