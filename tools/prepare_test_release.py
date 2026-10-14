"""Prepare a test release: download pinned mods, stage server/client files and build the client pack.

Usage: python tools/prepare_test_release.py v1.1.1t [--skip-build]
Outputs land in .artifacts/test-<version>/ (never committed).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
BASE_SERVER_SNAPSHOT = ROOT / "sources" / "BepInEx-server-1.1-sanitized.zip"
SKIPPED_NAMES = {"manifest.json", "icon.png", "readme.md", "changelog.md", "license", "license.txt", "license.md"}
SKIPPED_SUFFIXES = {".pdb", ".mdb"}
SIDES = {"both", "client", "server"}
COMPONENTS = {"patchers"}


class TestReleaseError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, destination: Path) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "akh-test-release/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    destination.write_bytes(data)
    return data


def safe_release_path(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or "\\" in value:
        raise TestReleaseError(f"Invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in value
    ):
        raise TestReleaseError(f"Unsafe {label}: {value!r}")
    return path


def fetch_mod(mod: dict, cache: Path) -> bytes:
    owner, name, version = mod["owner"], mod["name"], mod["version"]
    target = cache / f"{owner}-{name}-{version}.zip"
    if "sourceSnapshot" in mod:
        source_path = safe_release_path(mod["sourceSnapshot"], "sourceSnapshot")
        target_path = safe_release_path(mod.get("snapshotTarget"), "snapshotTarget")
        if [part.casefold() for part in source_path.parts[:2]] != ["bepinex", "plugins"]:
            raise TestReleaseError("sourceSnapshot must refer to a BepInEx/plugins file")
        try:
            with zipfile.ZipFile(BASE_SERVER_SNAPSHOT) as snapshot:
                payload = snapshot.read(source_path.as_posix())
        except KeyError as exc:
            raise TestReleaseError(f"Snapshot file not found: {source_path}") from exc
        digest = sha256_bytes(payload)
        if mod.get("sourceSha256") and mod["sourceSha256"] != digest:
            raise TestReleaseError(f"Source SHA-256 mismatch for {source_path}")
        mod["sourceSha256"] = digest
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            info = zipfile.ZipInfo(target_path.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
        data = buffer.getvalue()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data

    data = target.read_bytes() if target.exists() else download(
        f"https://thunderstore.io/package/download/{owner}/{name}/{version}/", target
    )
    digest = sha256_bytes(data)
    if mod.get("sha256") and mod["sha256"] != digest:
        target.unlink(missing_ok=True)
        raise TestReleaseError(f"SHA-256 mismatch for {owner}/{name} {version}")
    mod["sha256"] = digest
    return data


def runtime_files(mod: dict, data: bytes, work: Path) -> dict[str, bytes]:
    archive = zipfile.ZipFile(work)
    files: dict[str, bytes] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename)
        if ".." in path.parts or path.is_absolute():
            raise TestReleaseError(f"Unsafe path in {mod['name']}: {info.filename}")
        if path.name.lower() in SKIPPED_NAMES or path.suffix.lower() in SKIPPED_SUFFIXES:
            continue
        parts = list(path.parts)
        for prefix in (["BepInEx", "plugins"], ["plugins"]):
            if [part.lower() for part in parts[: len(prefix)]] == [p.lower() for p in prefix]:
                parts = parts[len(prefix) :]
                break
        if parts and parts[0].lower() == "config" and mod.get("configs") == "extract":
            files["@" + "/".join(parts)] = archive.read(info)
            continue
        if parts and parts[0].lower() == "patchers":
            components = mod.get("components", [])
            if "patchers" not in components or len(parts) < 2:
                raise TestReleaseError(f"{mod['name']} ships patchers/; review it manually")
            files["@patchers/" + "/".join(parts[1:])] = archive.read(info)
            continue
        if parts and parts[0].lower() in {"config", "monomod", "core"}:
            raise TestReleaseError(f"{mod['name']} ships {parts[0]}/; review it manually")
        if not parts:
            continue
        files["/".join(parts)] = archive.read(info)
    if not any(name.lower().endswith(".dll") for name in files):
        raise TestReleaseError(f"{mod['name']} contains no plugin DLL")
    return files


def write_files(root: Path, files: dict[str, bytes]) -> None:
    for relative, data in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def remove_excluded_plugins(plugin_root: Path, names: list[str]) -> None:
    excluded = {name.casefold() for name in names}
    if not excluded or not plugin_root.exists():
        return
    for path in sorted(plugin_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        in_thunderstore_cache = (
            plugin_root.name.casefold() == "server-thunderstore"
            or path.parent.name.casefold() == "thunderstore"
        )
        if path.is_dir() and path.name.casefold() in excluded:
            shutil.rmtree(path)
        elif path.is_file() and path.suffix.casefold() == ".dll" and path.stem.casefold() in excluded:
            path.unlink()
        elif (
            path.is_file()
            and in_thunderstore_cache
            and any(
                path.stem.casefold() == name
                or path.stem.casefold().startswith(f"{name}-")
                for name in excluded
            )
        ):
            path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Test version, for example v1.1.1t")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    release_dir = ROOT / "test-releases" / args.version
    manifest_path = release_dir / "mods.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["version"] != args.version:
        raise TestReleaseError("mods.json version does not match the requested version")

    out = ROOT / ".artifacts" / f"test-{args.version}"
    cache = out / "downloads"
    if out.joinpath("stage").exists():
        shutil.rmtree(out / "stage")
    cache.mkdir(parents=True, exist_ok=True)
    server_upload = out / "stage" / "server-upload"
    server_patchers = out / "stage" / "server-patchers"
    client_only = out / "stage" / "client-only-plugins"
    client_patchers: dict[str, bytes] = {}
    replacement_paths: set[str] = set()
    merged = out / "stage" / "server-merged"

    # Mods of earlier test releases (not yet in the base snapshot) are part of the merged tree
    # but are not uploaded again: the server already has them.
    inherited = []
    for previous in manifest.get("includes", []):
        inherited += json.loads((ROOT / "test-releases" / previous / "mods.json").read_text(encoding="utf-8"))["mods"]
    excluded = set(manifest.get("excludes", []))
    inherited = [m for m in inherited if m["name"] not in excluded]
    for mod in inherited + manifest["mods"]:
        is_new = mod in manifest["mods"]
        if mod["side"] not in SIDES:
            raise TestReleaseError(f"Invalid side for {mod['name']}")
        data = fetch_mod(mod, cache)
        zip_path = cache / f"{mod['owner']}-{mod['name']}-{mod['version']}.zip"
        files = runtime_files(mod, data, zip_path)
        config_files = {k[1:]: v for k, v in files.items() if k.startswith("@")}
        patcher_files = {k[len("@patchers/"):]: v for k, v in files.items() if k.startswith("@patchers/")}
        files = {k: v for k, v in files.items() if not k.startswith("@")}
        replace_existing = mod.get("replaceExisting", False)
        if not isinstance(replace_existing, bool):
            raise TestReleaseError(f"replaceExisting must be a boolean for {mod['name']}")
        plugin_dir = mod.get("pluginDir", mod["name"])
        if (
            not isinstance(plugin_dir, str)
            or not plugin_dir.strip()
            or plugin_dir in {".", ".."}
            or "/" in plugin_dir
            or "\\" in plugin_dir
            or ":" in plugin_dir
        ):
            raise TestReleaseError(f"Invalid pluginDir for {mod['name']}")
        if config_files and is_new:
            write_files(out / "stage" / "server-config", {k.split("/", 1)[1]: v for k, v in config_files.items()})
        if patcher_files:
            if mod["side"] in {"both", "server"} and is_new:
                write_files(server_patchers / plugin_dir, patcher_files)
            if mod["side"] in {"both", "client"}:
                for relative, data in patcher_files.items():
                    existing = client_patchers.get(relative)
                    if existing is not None and existing != data:
                        raise TestReleaseError(f"Conflicting client patcher file: {relative}")
                    client_patchers[relative] = data
        if mod["side"] in {"both", "server"}:
            if is_new:
                write_files(server_upload / plugin_dir, files)
            write_files(merged / "BepInEx" / "plugins" / plugin_dir, files)
            if is_new and replace_existing:
                replacement_paths.update(
                    f"{plugin_dir}/{relative}".casefold() for relative in files
                )
        if mod["side"] == "client":
            write_files(client_only / plugin_dir, files)
        print(f"{mod['side']:6} {mod['owner']}/{mod['name']} {mod['version']} ({len(files)} files)")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(BASE_SERVER_SNAPSHOT) as base:
        for info in base.infolist():
            if info.is_dir() or not info.filename.startswith("BepInEx/plugins/"):
                continue
            target = merged / info.filename
            if target.exists():
                relative = info.filename[len("BepInEx/plugins/"):].casefold()
                if relative in replacement_paths:
                    continue
                raise TestReleaseError(f"New mod overlaps a base file: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with base.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)

    excluded_plugins = manifest.get("excludePlugins", [])
    if not isinstance(excluded_plugins, list) or not all(
        isinstance(name, str) and name.strip() for name in excluded_plugins
    ):
        raise TestReleaseError("excludePlugins must be a list of non-empty plugin names")
    remove_excluded_plugins(merged / "BepInEx" / "plugins", excluded_plugins)
    remove_excluded_plugins(client_only, excluded_plugins)
    if client_patchers:
        write_files(out / "stage" / "client-patchers", client_patchers)

    if args.skip_build:
        return 0
    command = [
        sys.executable, str(ROOT / "tools" / "build_client_pack.py"),
        "--server-plugins", str(merged),
        "--version", args.version,
        "--output-dir", str(out / "release"),
    ]
    if client_only.exists():
        command += ["--plugin-overrides", str(client_only)]
    if client_patchers:
        command += ["--patcher-overrides", str(out / "stage" / "client-patchers")]
    if (out / "stage" / "server-config").exists():
        command += ["--server-config-folder", str(out / "stage" / "server-config")]
    return subprocess.call(command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
