"""Upload staged server plugin folders to the Valheim server over SFTP.

Usage: python tools/server_deploy.py v1.1.1t [--remove]
--remove deletes the folders of that release instead (rollback of new mods).
"""
import hashlib
import json
import errno
import sys
from pathlib import Path
from pathlib import PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sftp_recon

REMOTE_PLUGINS = "steamcmd/valheim/BepInEx/plugins"
REMOTE_PATCHERS = "steamcmd/valheim/BepInEx/patchers"
REMOTE_CONFIG = "steamcmd/valheim/BepInEx/config"
ROOT = Path(__file__).resolve().parents[1]


def mkdirs(sftp, path):
    current = ""
    for part in path.split("/"):
        current = f"{current}/{part}" if current else part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_sha256(sftp, path):
    digest = hashlib.sha256()
    with sftp.open(path, "rb") as source:
        source.prefetch(source.stat().st_size, max_concurrent_requests=32)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_if_changed(sftp, source, target):
    mkdirs(sftp, target.rsplit("/", 1)[0])
    source_hash = file_sha256(source)
    try:
        current = sftp.stat(target)
    except IOError as exc:
        if getattr(exc, "errno", None) != errno.ENOENT:
            raise
        current = None
    if (
        current is not None
        and current.st_size == source.stat().st_size
        and remote_sha256(sftp, target) == source_hash
    ):
        return False

    sftp.put(str(source), target)
    current = sftp.stat(target)
    if current.st_size != source.stat().st_size or remote_sha256(sftp, target) != source_hash:
        raise SystemExit(f"remote SHA-256 mismatch: {target}")
    return True


def rmtree(sftp, path, failures):
    import stat
    try:
        entries = sftp.listdir_attr(path)
    except IOError as exc:
        if getattr(exc, "errno", None) == errno.ENOENT:
            return
        failures.append(f"{path}: {exc}")
        return
    for entry in entries:
        child = f"{path}/{entry.filename}"
        if stat.S_ISDIR(entry.st_mode):
            rmtree(sftp, child, failures)
        else:
            try:
                sftp.remove(child)
            except IOError as exc:
                if getattr(exc, "errno", None) != errno.ENOENT:
                    failures.append(f"{child}: {exc}")
    try:
        sftp.rmdir(path)
    except IOError as exc:
        if getattr(exc, "errno", None) != errno.ENOENT:
            failures.append(f"{path}: {exc}")


def remote_file_map(sftp, root):
    import stat
    files = {}

    def walk(directory, prefix=""):
        for entry in sftp.listdir_attr(directory):
            remote = f"{directory}/{entry.filename}"
            relative = f"{prefix}/{entry.filename}" if prefix else entry.filename
            if stat.S_ISDIR(entry.st_mode):
                walk(remote, relative)
            elif stat.S_ISREG(entry.st_mode):
                files[relative] = (remote, entry.st_size)

    walk(root)
    return files


def verify_provider_cache_empty(sftp):
    remote = f"{REMOTE_PLUGINS}/thunderstore"
    try:
        actual = remote_file_map(sftp, remote)
    except IOError as exc:
        if getattr(exc, "errno", None) != errno.ENOENT:
            raise
        actual = {}
    if actual:
        remaining = ", ".join(sorted(actual)[:5])
        raise SystemExit(
            "Provider-managed thunderstore cache is not empty; remove its mods from "
            f"the provider list before deploying (found: {remaining})."
        )
    print("verified provider-managed plugin cache is empty")


def remove_excluded_plugins(sftp, names):
    import stat
    failures = []
    for name in names:
        if not isinstance(name, str) or not name.strip() or "/" in name or "\\" in name:
            raise SystemExit(f"Invalid excluded plugin name: {name!r}")
        for remote in (f"{REMOTE_PLUGINS}/{name}", f"{REMOTE_PLUGINS}/{name}.dll"):
            try:
                attributes = sftp.stat(remote)
            except IOError as exc:
                if getattr(exc, "errno", None) != errno.ENOENT:
                    failures.append(f"{remote}: {exc}")
                continue
            if stat.S_ISDIR(attributes.st_mode):
                rmtree(sftp, remote, failures)
            else:
                try:
                    sftp.remove(remote)
                except IOError as exc:
                    failures.append(f"{remote}: {exc}")
            if not any(item.startswith(remote + "/") or item.startswith(remote + ":") for item in failures):
                print(f"removed {remote}")
    return failures


def main():
    version = sys.argv[1]
    remove = "--remove" in sys.argv
    upload = ROOT / ".artifacts" / f"test-{version}" / "stage" / "server-upload"
    patchers = ROOT / ".artifacts" / f"test-{version}" / "stage" / "server-patchers"
    config_stage = ROOT / ".artifacts" / f"test-{version}" / "stage" / "server-config"
    overrides = ROOT / "client-pack" / "AKHPlugins" / "customizations" / "BepInEx" / "config"
    transport, sftp = sftp_recon.connect()
    try:
        manifest = None
        if not remove:
            manifest = json.loads(
                (ROOT / "test-releases" / version / "mods.json").read_text(encoding="utf-8")
            )
            verify_provider_cache_empty(sftp)

        uploaded = 0
        unchanged = 0
        for folder in sorted(p for p in upload.iterdir() if p.is_dir()):
            remote = f"{REMOTE_PLUGINS}/{folder.name}"
            if remove:
                try:
                    failures = []
                    rmtree(sftp, remote, failures)
                    if failures:
                        raise SystemExit("Could not remove staged plugin files: " + "; ".join(failures))
                    print(f"removed {remote}")
                except IOError:
                    print(f"absent {remote}")
                continue
            for file in sorted(p for p in folder.rglob("*") if p.is_file()):
                target = f"{remote}/{file.relative_to(folder).as_posix()}"
                changed = upload_if_changed(sftp, file, target)
                uploaded += int(changed)
                unchanged += int(not changed)
        if patchers.exists():
            for folder in sorted(p for p in patchers.iterdir() if p.is_dir()):
                for file in sorted(p for p in folder.rglob("*") if p.is_file()):
                    target = f"{REMOTE_PATCHERS}/{file.relative_to(folder).as_posix()}"
                    if remove:
                        try:
                            sftp.remove(target)
                            print(f"removed {target}")
                        except IOError as exc:
                            if getattr(exc, "errno", None) not in {2, 13}:
                                raise
                            print(f"could not remove {target}: {exc}")
                        continue
                    changed = upload_if_changed(sftp, file, target)
                    uploaded += int(changed)
                    unchanged += int(not changed)
        if not remove:
            removal_failures = remove_excluded_plugins(sftp, manifest.get("excludePlugins", []))
        if not remove and config_stage.exists():
            for file in sorted(p for p in config_stage.rglob("*") if p.is_file()):
                relative = file.relative_to(config_stage)
                source = overrides / relative if (overrides / relative).exists() else file
                target = f"{REMOTE_CONFIG}/{relative.as_posix()}"
                mkdirs(sftp, target.rsplit("/", 1)[0])
                sftp.put(str(source), target)
                if sftp.stat(target).st_size != source.stat().st_size:
                    raise SystemExit(f"size mismatch {target}")
                print(f"uploaded {target} (from {source.name} in {source.parent.name})")
        if not remove:
            for relative in manifest.get("serverTranslations", []):
                if not isinstance(relative, str):
                    raise SystemExit(f"Invalid server translation path: {relative!r}")
                normalized = relative.replace("\\", "/")
                if (
                    not (
                        normalized.startswith("BepInEx/plugins/")
                        or normalized.startswith("BepInEx/config/")
                    )
                    or any(part in {"", ".", ".."} for part in normalized.split("/"))
                    or ":" in normalized
                ):
                    raise SystemExit(f"Invalid server translation path: {relative!r}")
                source = ROOT / "client-pack" / "AKHPlugins" / "customizations" / Path(*normalized.split("/"))
                if not source.is_file() and normalized.startswith("BepInEx/config/"):
                    source = config_stage / Path(*normalized[len("BepInEx/config/"):].split("/"))
                if not source.is_file():
                    raise SystemExit(f"Missing server translation: {source}")
                if normalized.startswith("BepInEx/plugins/"):
                    target = f"{REMOTE_PLUGINS}/{normalized[len('BepInEx/plugins/'):]}"
                else:
                    target = f"{REMOTE_CONFIG}/{normalized[len('BepInEx/config/'):]}"
                changed = upload_if_changed(sftp, source, target)
                uploaded += int(changed)
                unchanged += int(not changed)
            if removal_failures:
                raise SystemExit(
                    "Excluded plugins could not all be removed: " + "; ".join(removal_failures)
                )
        print(f"server files synchronized: {uploaded} uploaded, {unchanged} unchanged")
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    main()
