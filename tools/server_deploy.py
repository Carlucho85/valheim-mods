"""Upload staged server plugin folders to the Valheim server over SFTP.

Usage: python tools/server_deploy.py v1.1.1t [--remove]
--remove deletes the folders of that release instead (rollback of new mods).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sftp_recon

REMOTE_PLUGINS = "steamcmd/valheim/BepInEx/plugins"
ROOT = Path(__file__).resolve().parents[1]


def mkdirs(sftp, path):
    current = ""
    for part in path.split("/"):
        current = f"{current}/{part}" if current else part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def rmtree(sftp, path):
    import stat
    for entry in sftp.listdir_attr(path):
        child = f"{path}/{entry.filename}"
        if stat.S_ISDIR(entry.st_mode):
            rmtree(sftp, child)
        else:
            sftp.remove(child)
    sftp.rmdir(path)


def main():
    version = sys.argv[1]
    remove = "--remove" in sys.argv
    upload = ROOT / ".artifacts" / f"test-{version}" / "stage" / "server-upload"
    transport, sftp = sftp_recon.connect()
    try:
        for folder in sorted(p for p in upload.iterdir() if p.is_dir()):
            remote = f"{REMOTE_PLUGINS}/{folder.name}"
            if remove:
                try:
                    rmtree(sftp, remote)
                    print(f"removed {remote}")
                except IOError:
                    print(f"absent {remote}")
                continue
            for file in sorted(p for p in folder.rglob("*") if p.is_file()):
                target = f"{remote}/{file.relative_to(folder).as_posix()}"
                mkdirs(sftp, target.rsplit("/", 1)[0])
                sftp.put(str(file), target)
                if sftp.stat(target).st_size != file.stat().st_size:
                    raise SystemExit(f"size mismatch {target}")
                print(f"uploaded {target}")
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    main()
