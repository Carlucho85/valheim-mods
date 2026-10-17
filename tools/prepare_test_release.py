"""Prepare a test release: download pinned mods, stage server/client files and build the client pack.

Usage: python tools/prepare_test_release.py v1.1.1t [--skip-build]
Outputs land in .artifacts/test-<version>/ (never committed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from shutil import copyfileobj
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
BASE_SERVER_SNAPSHOT = ROOT / "sources" / "BepInEx-server-1.1-sanitized.zip"
REPOSITORY = "Carlucho85/valheim-mods"
SKIPPED_NAMES = {"manifest.json", "icon.png", "readme.md", "changelog.md", "license", "license.txt", "license.md"}
SKIPPED_SUFFIXES = {".pdb", ".mdb"}
SIDES = {"both", "client", "server"}


class TestReleaseError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, destination: Path) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "akh-test-release/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return data


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "akh-test-release/1.0"})
    temporary = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            copyfileobj(response, output, 1024 * 1024)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_base_client_plugins(archive_path: Path, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    copied = 0
    has_plugin_dll = False
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir():
                name = name.rstrip("/")
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or re.match(r"^[A-Za-z]:", name)
                or any(part in {"", ".", ".."} for part in name.split("/"))
            ):
                raise TestReleaseError(f"Unsafe path in base client package: {info.filename}")
            if info.is_dir() or len(path.parts) < 3:
                continue
            if [part.casefold() for part in path.parts[:2]] != ["bepinex", "plugins"]:
                continue
            relative = path.parts[2:]
            if relative[0].casefold() == "akhplugins":
                continue
            key = "/".join(relative).casefold()
            if key in seen:
                raise TestReleaseError(f"Duplicate path in base client package: {info.filename}")
            seen.add(key)
            target = destination / "BepInEx" / "plugins" / Path(*relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                copyfileobj(source, output, 1024 * 1024)
            copied += 1
            has_plugin_dll |= target.suffix.casefold() == ".dll"
    if not copied or not has_plugin_dll:
        raise TestReleaseError("Base client package contains no usable plugin files.")
    return copied


def stage_stable_client_base(release: str, base_dir: Path, destination: Path) -> int:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", release):
        raise TestReleaseError(f"Invalid stable client release tag: {release}")
    base_url = f"https://github.com/{REPOSITORY}/releases/download/{release}"
    manifest_path = base_dir / "client-manifest.json"
    if not manifest_path.exists():
        download(f"{base_url}/client-manifest.json", manifest_path)
    try:
        client_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TestReleaseError(f"Invalid base client manifest for {release}: {exc}") from exc
    if (
        not isinstance(client_manifest, dict)
        or client_manifest.get("version") != release
        or client_manifest.get("archiveName") != "valheim-mods-cliente.zip"
        or not isinstance(client_manifest.get("archiveSha256"), str)
        or not re.fullmatch(r"[a-fA-F0-9]{64}", client_manifest["archiveSha256"])
    ):
        raise TestReleaseError(f"Unexpected client manifest metadata for {release}")
    archive_path = base_dir / client_manifest["archiveName"]
    if not archive_path.exists():
        download_file(f"{base_url}/{client_manifest['archiveName']}", archive_path)
    if archive_path.stat().st_size != client_manifest.get("archiveSize"):
        raise TestReleaseError(f"Base client package size mismatch for {release}")
    if sha256_file(archive_path).lower() != client_manifest["archiveSha256"].lower():
        raise TestReleaseError(f"Base client package SHA-256 mismatch for {release}")
    return stage_base_client_plugins(archive_path, destination)


def fetch_mod(mod: dict, cache: Path) -> bytes:
    owner, name, version = mod["owner"], mod["name"], mod["version"]
    target = cache / f"{owner}-{name}-{version}.zip"
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
        if parts and parts[0].lower() in {"config", "patchers", "monomod", "core"}:
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
    server_upload.mkdir(parents=True, exist_ok=True)
    client_only = out / "stage" / "client-only-plugins"
    merged = out / "stage" / "server-merged"

    base_client_release = manifest.get("baseClientRelease")
    if base_client_release:
        if base_client_release != manifest.get("base"):
            raise TestReleaseError("baseClientRelease must match the release's base.")
        if manifest.get("includes") or manifest.get("excludes") or manifest["mods"]:
            raise TestReleaseError(
                "Stable-client-base releases cannot include additional mods in this mode."
            )
        copied = stage_stable_client_base(base_client_release, out / "base", merged)
        print(f"client base {base_client_release}: staged {copied} plugin files")
    else:
        # Earlier test releases are additions to the sanitized 1.1 server snapshot.
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
            files = {k: v for k, v in files.items() if not k.startswith("@")}
            if config_files and is_new:
                write_files(out / "stage" / "server-config", {k.split("/", 1)[1]: v for k, v in config_files.items()})
            if mod["side"] in {"both", "server"}:
                if is_new:
                    write_files(server_upload / mod["name"], files)
                write_files(merged / "BepInEx" / "plugins" / mod["name"], files)
            if mod["side"] == "client":
                write_files(client_only / mod["name"], files)
            print(f"{mod['side']:6} {mod['owner']}/{mod['name']} {mod['version']} ({len(files)} files)")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not base_client_release:
        with zipfile.ZipFile(BASE_SERVER_SNAPSHOT) as base:
            for info in base.infolist():
                if info.is_dir() or not info.filename.startswith("BepInEx/plugins/"):
                    continue
                target = merged / info.filename
                if target.exists():
                    raise TestReleaseError(f"New mod overlaps a base file: {info.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with base.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)

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
    readme_path = release_dir / "README.txt"
    if readme_path.exists():
        command += ["--readme", str(readme_path)]
    return subprocess.call(command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
