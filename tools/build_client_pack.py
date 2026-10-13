#!/usr/bin/env python3
"""Build the public Windows client package from a server plugins.zip."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "client-pack" / "overrides"
LOADER_INFO = ROOT / "client-pack" / "bepinex-pack.json"
README = ROOT / "client-pack" / "README.txt"
SERVER_CONFIG_ALLOWLIST = ROOT / "client-pack" / "server-config-allowlist.txt"
PACKAGE_NAME = "valheim-mods-cliente.zip"
MANIFEST_NAME = "client-manifest.json"
PACKAGE_MANIFEST_NAME = "client-pack-manifest.json"
SENSITIVE_PLUGIN_CONFIGS = {"quickconnectserverscfg"}
SERVER_ONLY_PLUGIN_DLLS = {"maxplayercount.dll"}
# Duplicate Thunderstore package artwork; Windows treats these case variants as one path.
NON_RUNTIME_DUPLICATE_FILES = {"thunderstore/IconNX.png"}
ARCHIVE_METADATA = {
    "__folder_managed_by_vortex",
    "manifest.json",
    "vortex.deployment.json",
    "vortex.deployment.bepinex-dll-modtype.json",
}
TEXT_DOC_SUFFIXES = {".md", ".pdb", ".mdb"}
IGNORED_DOC_NAMES = {"readme.md", "changelog.md", "changelog.txt"}
# The server log identifies these Thunderstore copies as newer/active than the
# stale DLLs left in the installed plugin folders.
THUNDERSTORE_PREFERRED_DLLS = {
    "adventurebackpacks.dll",
    "ammocount.dll",
    "bepinex.configdrawers.dll",
    "dooropenerbruh.dll",
    "minimalstatuseffects.dll",
    "advize_planteasily.dll",
    "shieldmebruh.dll",
}


class PackageError(RuntimeError):
    """An unsafe or inconsistent input package."""


def is_quick_connect_path(path: str) -> bool:
    for component in path.replace("\\", "/").casefold().split("/"):
        normalized = re.sub(r"[^a-z0-9]", "", component)
        stem = re.sub(r"[^a-z0-9]", "", PurePosixPath(component).stem)
        if normalized == "quickconnect" or stem == "quickconnect":
            return True
    return False


def is_sensitive_plugin_config(path: str) -> bool:
    basename = PurePosixPath(path.replace("\\", "/")).name.casefold()
    normalized = re.sub(r"[^a-z0-9]", "", basename)
    return normalized in SENSITIVE_PLUGIN_CONFIGS


def plugin_relative_path(path: str) -> str | None:
    normalized = safe_archive_path(path)
    for prefix in ("BepInEx/plugins/", "plugins/"):
        if normalized.casefold().startswith(prefix.casefold()):
            return normalized[len(prefix) :]
    return None


def is_stale_adventure_backpacks_file(
    relative: str, thunderstore_dll_names: set[str]
) -> bool:
    return (
        relative.casefold().split("/", 1)[0] == "adventurebackpacks"
        and "adventurebackpacks.dll" in thunderstore_dll_names
    )


def is_stale_preferred_plugin_dll(
    relative: str, thunderstore_dll_names: set[str]
) -> bool:
    basename = PurePosixPath(relative).name.casefold()
    return (
        not relative.casefold().startswith("thunderstore/")
        and basename in THUNDERSTORE_PREFERRED_DLLS
        and basename in thunderstore_dll_names
    )


class DirectoryArchive:
    """Expose a server plugins directory through the ZIP-reader interface."""

    def __init__(self, root: Path) -> None:
        root = root.resolve()
        candidates = (root / "BepInEx" / "plugins", root / "plugins")
        self.plugins_root = next((path for path in candidates if path.is_dir()), root)
        self._files: dict[str, Path] = {}
        self._members: list[zipfile.ZipInfo] = []
        for path in sorted(self.plugins_root.rglob("*")):
            if path.is_symlink():
                raise PackageError(f"Symbolic links are not allowed in the plugins directory: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(self.plugins_root).as_posix()
            member_name = safe_archive_path(f"plugins/{relative}")
            member = zipfile.ZipInfo(member_name)
            member.file_size = path.stat().st_size
            self._members.append(member)
            self._files[member_name] = path

    def __enter__(self) -> DirectoryArchive:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def infolist(self) -> list[zipfile.ZipInfo]:
        return self._members

    def open(self, member: zipfile.ZipInfo) -> Any:
        return self._files[member.filename].open("rb")

    def read(self, member: zipfile.ZipInfo) -> bytes:
        with self.open(member) as source:
            return source.read()


def open_server_source(path: Path) -> zipfile.ZipFile | DirectoryArchive:
    if path.is_dir():
        return DirectoryArchive(path)
    try:
        return zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackageError(f"Cannot open server plugins ZIP or folder: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_zip_member(
    archive: zipfile.ZipFile | DirectoryArchive, member: zipfile.ZipInfo
) -> str:
    digest = hashlib.sha256()
    with archive.open(member) as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_bytes(value: bytes, label: str) -> Any:
    try:
        return json.loads(value.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"{label} is not valid UTF-8 JSON: {exc}") from exc


def safe_archive_path(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise PackageError(f"Unsafe archive path: {name!r}")
    if re.match(r"^[A-Za-z]:", normalized):
        raise PackageError(f"Drive-qualified archive path: {name!r}")
    return normalized


def is_document_or_metadata(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    suffix = PurePosixPath(path).suffix.lower()
    return (
        name in ARCHIVE_METADATA
        or name in IGNORED_DOC_NAMES
        or suffix in TEXT_DOC_SUFFIXES
        or name.endswith(".pdb")
        or name.endswith(".mdb")
    )


def discover_server_files(
    archive: zipfile.ZipFile | DirectoryArchive,
) -> list[tuple[zipfile.ZipInfo, str]]:
    files: list[tuple[zipfile.ZipInfo, str]] = []
    direct_dll_names: set[str] = set()
    direct_sidecar_names: set[str] = set()
    thunderstore_dll_names: set[str] = set()

    for member in archive.infolist():
        if member.is_dir():
            continue
        relative = plugin_relative_path(member.filename)
        if relative is None:
            continue
        if not relative or is_document_or_metadata(relative):
            continue
        if is_quick_connect_path(relative):
            continue
        if relative in NON_RUNTIME_DUPLICATE_FILES:
            continue
        lower = relative.lower()
        basename = PurePosixPath(relative).name.lower()
        if is_sensitive_plugin_config(relative):
            continue
        if lower.startswith("thunderstore/") and basename.endswith(".dll"):
            thunderstore_dll_names.add(basename)

    for member in archive.infolist():
        if member.is_dir():
            continue
        relative = plugin_relative_path(member.filename)
        if relative is None:
            continue
        if not relative or is_document_or_metadata(relative):
            continue
        if is_quick_connect_path(relative):
            continue
        if is_stale_adventure_backpacks_file(
            relative, thunderstore_dll_names
        ) or is_stale_preferred_plugin_dll(relative, thunderstore_dll_names):
            continue
        if relative in NON_RUNTIME_DUPLICATE_FILES:
            continue
        lower = relative.lower()
        basename = PurePosixPath(relative).name.lower()
        if is_sensitive_plugin_config(relative):
            continue
        if not lower.startswith("thunderstore/"):
            if basename.endswith(".dll"):
                direct_dll_names.add(basename)
            elif (
                basename.startswith("adventurebackpacks.")
                or basename.startswith("xportal-")
                or basename == "translations.json"
            ):
                direct_sidecar_names.add(basename)

    for member in archive.infolist():
        if member.is_dir():
            continue
        relative = plugin_relative_path(member.filename)
        if relative is None:
            continue
        if not relative or is_document_or_metadata(relative):
            continue
        if is_quick_connect_path(relative):
            continue
        if is_stale_adventure_backpacks_file(
            relative, thunderstore_dll_names
        ) or is_stale_preferred_plugin_dll(relative, thunderstore_dll_names):
            continue
        if relative in NON_RUNTIME_DUPLICATE_FILES:
            continue
        lower = relative.lower()
        basename = PurePosixPath(relative).name.lower()
        if is_sensitive_plugin_config(relative):
            continue
        if basename in SERVER_ONLY_PLUGIN_DLLS and basename.endswith(".dll"):
            continue
        if lower.startswith("thunderstore/"):
            if (
                basename.endswith(".dll")
                and basename in direct_dll_names
                and basename not in THUNDERSTORE_PREFERRED_DLLS
            ):
                continue
            if (
                (
                    basename.startswith("adventurebackpacks.")
                    or basename.startswith("xportal-")
                    or basename == "translations.json"
                )
                and basename in direct_sidecar_names
            ):
                continue
        files.append((member, "BepInEx/plugins/" + relative))

    paths: set[str] = set()
    dlls: set[str] = set()
    for _, output_path in files:
        key = output_path.casefold()
        if key in paths:
            raise PackageError(f"Duplicate client package path: {output_path}")
        paths.add(key)
        if output_path.lower().endswith(".dll"):
            dll_key = PurePosixPath(output_path).name.casefold()
            if dll_key in dlls:
                raise PackageError(f"Conflicting plugin DLL basename: {output_path}")
            dlls.add(dll_key)
    if not dlls:
        raise PackageError(
            "The server archive contains no plugin DLLs under plugins/ or BepInEx/plugins/."
        )
    return files


def load_overrides() -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    replacements: dict[str, bytes] = {}
    merges: dict[str, dict[str, Any]] = {}
    for path in sorted(OVERRIDES.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(OVERRIDES).as_posix()
        if is_quick_connect_path(relative):
            raise PackageError(f"Quick Connect cannot be included in client overrides: {relative}")
        if relative.endswith(".overrides.json"):
            target = relative[: -len(".overrides.json")]
            if not target.lower().endswith(".json"):
                raise PackageError(f"JSON overlay must target a JSON file: {relative}")
            data = read_json_bytes(path.read_bytes(), relative)
            if not isinstance(data, dict):
                raise PackageError(f"JSON overlay must contain an object: {relative}")
            merges[target] = data
        else:
            replacements[relative] = path.read_bytes()
    return replacements, merges


def load_plugin_overrides(plugin_dir: Path | None) -> dict[str, bytes]:
    if plugin_dir is None:
        return {}
    if not plugin_dir.is_dir():
        raise PackageError(f"Plugin override folder does not exist: {plugin_dir}")
    result: dict[str, bytes] = {}
    for source in sorted(plugin_dir.rglob("*")):
        if source.is_symlink():
            raise PackageError(f"Symbolic links are not allowed in plugin overrides: {source}")
        if not source.is_file():
            continue
        relative = source.relative_to(plugin_dir).as_posix()
        if is_quick_connect_path(relative):
            continue
        if is_sensitive_plugin_config(relative):
            raise PackageError(f"Sensitive plugin config cannot be included in the client package: {relative}")
        safe_archive_path(relative)
        output_path = f"BepInEx/plugins/{relative}"
        result[output_path] = source.read_bytes()
    return result


def load_server_configs(config_dir: Path | None, allowlist_path: Path) -> dict[str, bytes]:
    try:
        allowlist = allowlist_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise PackageError(f"Cannot read server config allowlist {allowlist_path}: {exc}") from exc

    relative_paths: list[str] = []
    seen: set[str] = set()
    for line in allowlist:
        relative = line.split("#", 1)[0].strip()
        if not relative:
            continue
        relative = safe_archive_path(relative)
        if is_sensitive_plugin_config(relative):
            raise PackageError(f"Sensitive server config cannot be shared: {relative}")
        key = relative.casefold()
        if key in seen:
            raise PackageError(f"Duplicate server config allowlist entry: {relative}")
        seen.add(key)
        if PurePosixPath(relative).suffix.lower() not in {".cfg", ".ini", ".json", ".xml", ".yaml", ".yml"}:
            raise PackageError(f"Unsupported server config file type: {relative}")
        relative_paths.append(relative)

    if relative_paths and config_dir is None:
        raise PackageError("The config allowlist is populated; pass --server-config-folder.")
    if config_dir is None:
        return {}
    if not config_dir.is_dir():
        raise PackageError(f"Server config folder does not exist: {config_dir}")

    root = config_dir.resolve()
    result: dict[str, bytes] = {}
    for relative in relative_paths:
        source = root.joinpath(*PurePosixPath(relative).parts)
        if source.is_symlink() or not source.is_file():
            raise PackageError(f"Allowlisted server config file is missing or unsafe: {relative}")
        resolved = source.resolve()
        if not resolved.is_relative_to(root):
            raise PackageError(f"Server config path escapes its folder: {relative}")
        result[f"BepInEx/config/{relative}"] = source.read_bytes()
    return result


def transform_source_file(
    archive: zipfile.ZipFile | DirectoryArchive,
    member: zipfile.ZipInfo | None,
    output_path: str,
    replacements: dict[str, bytes],
    merges: dict[str, dict[str, Any]],
    base_data: bytes | None = None,
) -> bytes | None:
    if output_path in merges:
        if output_path in replacements:
            source_data = replacements[output_path]
        elif base_data is not None:
            source_data = base_data
        elif member is not None:
            source_data = archive.read(member)
        else:
            raise PackageError(f"Cannot merge JSON overlay without a source file: {output_path}")
        base = read_json_bytes(source_data, output_path)
        if not isinstance(base, dict):
            raise PackageError(f"Cannot merge localization into non-object JSON: {output_path}")
        base.update(merges[output_path])
        return (json.dumps(base, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output_path in replacements:
        return replacements[output_path]
    return base_data


def get_loader_archive(output: Path, supplied: Path | None) -> tuple[Path, dict[str, Any]]:
    try:
        loader_info = json.loads(LOADER_INFO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"Cannot read loader metadata {LOADER_INFO}: {exc}") from exc
    target = output / loader_info["archiveName"]
    if supplied:
        shutil.copyfile(supplied, target)
    else:
        request = urllib.request.Request(
            loader_info["url"],
            headers={"User-Agent": "AkaiHoshi-Valheim-Packager/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as dest:
                shutil.copyfileobj(response, dest, 1024 * 1024)
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise PackageError(f"Could not download the official BepInEx pack: {exc}") from exc
    actual_hash = sha256_file(target)
    if actual_hash.lower() != loader_info["sha256"].lower():
        target.unlink(missing_ok=True)
        raise PackageError(
            f"BepInEx pack SHA-256 mismatch: expected {loader_info['sha256']}, got {actual_hash}"
        )
    with zipfile.ZipFile(target) as loader:
        names = {safe_archive_path(info.filename) for info in loader.infolist() if not info.is_dir()}
    if not any(name.endswith("/BepInEx/core/BepInEx.dll") for name in names):
        raise PackageError("The verified BepInEx archive does not contain its loader assembly.")
    return target, loader_info


def write_package(
    server_zip: Path,
    output_dir: Path,
    version: str,
    loader_archive: Path | None = None,
    server_config_dir: Path | None = None,
    config_allowlist: Path = SERVER_CONFIG_ALLOWLIST,
    plugin_override_dir: Path | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise PackageError("Version must be a semantic version tag such as v1.0.0.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not server_zip.is_file() and not server_zip.is_dir():
        raise PackageError(f"Server plugins ZIP or folder does not exist: {server_zip}")

    loader_path, loader_info = get_loader_archive(output_dir, loader_archive)
    replacements, merges = load_overrides()
    plugin_overrides = load_plugin_overrides(plugin_override_dir)
    server_configs = load_server_configs(server_config_dir, config_allowlist)
    package_path = output_dir / PACKAGE_NAME
    package_files: list[dict[str, Any]] = []
    file_entries: list[tuple[zipfile.ZipInfo, str, bytes | None, str]] = []
    with open_server_source(server_zip) as source:
        selected = discover_server_files(source)
        used: set[str] = set()
        for member, output_path in selected:
            data = transform_source_file(
                source,
                member,
                output_path,
                replacements,
                merges,
                plugin_overrides.get(output_path),
            )
            digest = hashlib.sha256(data).hexdigest() if data is not None else sha256_zip_member(source, member)
            size = len(data) if data is not None else member.file_size
            key = output_path.casefold()
            if key in used:
                raise PackageError(f"An overlay or source file duplicates {output_path}")
            used.add(key)
            file_entries.append((member, output_path, data, digest))
            package_files.append({"path": output_path, "sha256": digest, "size": size})

        for output_path, override_data in sorted(plugin_overrides.items()):
            if output_path.casefold() in used:
                continue
            data = transform_source_file(
                source, None, output_path, replacements, merges, override_data
            )
            if data is None:
                continue
            key = output_path.casefold()
            if key in used:
                raise PackageError(f"Duplicate client package path: {output_path}")
            used.add(key)
            file_entries.append((zipfile.ZipInfo(output_path), output_path, data, hashlib.sha256(data).hexdigest()))
            package_files.append({"path": output_path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})

        for output_path, server_data in sorted(server_configs.items()):
            data = transform_source_file(
                source, None, output_path, replacements, merges, server_data
            )
            if data is None:
                continue
            key = output_path.casefold()
            if key in used:
                raise PackageError(f"Duplicate client package path: {output_path}")
            used.add(key)
            file_entries.append((zipfile.ZipInfo(output_path), output_path, data, hashlib.sha256(data).hexdigest()))
            package_files.append({"path": output_path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})

    selected_paths = {output_path.casefold() for _, output_path in selected}
    for output_path, data in sorted(replacements.items()):
        safe_archive_path(output_path)
        if output_path.casefold() in used or output_path.casefold() in selected_paths:
            continue
        file_entries.append((zipfile.ZipInfo(output_path), output_path, data, hashlib.sha256(data).hexdigest()))
        package_files.append(
            {"path": output_path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        )

    package_files.sort(key=lambda entry: entry["path"].casefold())
    package_manifest = {
        "schemaVersion": 1,
        "version": version,
        "files": package_files,
    }
    manifest_bytes = (json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with open_server_source(server_zip) as source, zipfile.ZipFile(
        package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
    ) as output:
        seen: set[str] = set()
        for member, output_path, data, _ in file_entries:
            target = "BepInEx/plugins/" + output_path[len("BepInEx/plugins/") :] if output_path.startswith("BepInEx/plugins/") else output_path
            key = target.casefold()
            if key in seen:
                raise PackageError(f"Duplicate package archive path: {target}")
            seen.add(key)
            if data is not None:
                output.writestr(target, data)
            else:
                with source.open(member) as src, output.open(target, "w", force_zip64=True) as dest:
                    shutil.copyfileobj(src, dest, 1024 * 1024)
        readme_path = "README.txt"
        readme_data = README.read_bytes()
        output.writestr(readme_path, readme_data)
        output.writestr(PACKAGE_MANIFEST_NAME, manifest_bytes)

    package_hash = sha256_file(package_path)
    package_size = package_path.stat().st_size
    loader_hash = sha256_file(loader_path)
    manifest = {
        "schemaVersion": 1,
        "version": version,
        "game": "Valheim",
        "archiveName": PACKAGE_NAME,
        "archiveSha256": package_hash,
        "archiveSize": package_size,
        "expandedSize": sum(file["size"] for file in package_files) + len(manifest_bytes) + len(readme_data),
        "fileCount": len(package_files),
        "pluginDllCount": sum(file["path"].lower().endswith(".dll") for file in package_files),
        "loaderVersion": loader_info["version"],
        "loaderArchiveName": loader_path.name,
        "loaderSha256": loader_hash,
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{PACKAGE_NAME}.sha256").write_text(
        f"{package_hash}  {PACKAGE_NAME}\n", encoding="ascii"
    )
    (output_dir / f"{loader_path.name}.sha256").write_text(
        f"{loader_hash}  {loader_path.name}\n", encoding="ascii"
    )

    with zipfile.ZipFile(package_path) as package:
        bad = package.testzip()
        if bad:
            raise PackageError(f"Generated ZIP failed CRC verification at {bad}")
        if package.read(PACKAGE_MANIFEST_NAME) != manifest_bytes:
            raise PackageError("Embedded package manifest did not round-trip.")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-plugins",
        type=Path,
        required=True,
        help="BepInEx/plugins ZIP or folder supplied by the administrator",
    )
    parser.add_argument("--version", required=True, help="Release version tag, for example v1.0.0")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".artifacts" / "client-release")
    parser.add_argument("--bepinex-archive", type=Path, help="Optional local copy of the pinned Thunderstore BepInEx ZIP")
    parser.add_argument(
        "--server-config-folder",
        type=Path,
        help="Optional BepInEx/config folder; only entries in the config allowlist are packaged",
    )
    parser.add_argument(
        "--config-allowlist",
        type=Path,
        default=SERVER_CONFIG_ALLOWLIST,
        help="Text file listing client-safe server configs to package",
    )
    parser.add_argument(
        "--plugin-overrides",
        type=Path,
        help="Optional folder of BepInEx/plugins files that replace or supplement server plugins",
    )
    args = parser.parse_args()
    try:
        result = write_package(
            args.server_plugins,
            args.output_dir,
            args.version,
            args.bepinex_archive,
            args.server_config_folder,
            args.config_allowlist,
            args.plugin_overrides,
        )
    except (PackageError, OSError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Release assets prepared in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
