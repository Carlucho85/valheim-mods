"""Download remote folders to a local backup dir (read-only on the server)."""
import stat
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sftp_recon

BACKUPS = Path(r"C:\Users\Carlucho\Documents\akh-backups")
TARGETS = ["steamcmd/valheim/BepInEx/plugins", "steamcmd/valheim/BepInEx/config",
           "steamcmd/valheim/BepInEx/patchers", ".config/unity3d"]


def pull(sftp, remote, local, counter):
    local.mkdir(parents=True, exist_ok=True)
    for entry in sftp.listdir_attr(remote):
        r = remote + "/" + entry.filename
        l = local / entry.filename
        if stat.S_ISDIR(entry.st_mode):
            pull(sftp, r, l, counter)
        else:
            sftp.get(r, str(l))
            counter[0] += 1
            counter[1] += entry.st_size


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "stable-1.1.0"
    dest = BACKUPS / f"{datetime.now():%Y%m%d-%H%M%S}-{label}"
    transport, sftp = sftp_recon.connect()
    counter = [0, 0]
    try:
        for target in TARGETS:
            pull(sftp, target, dest / target, counter)
    finally:
        sftp.close()
        transport.close()
    print(f"{dest}: {counter[0]} files, {counter[1] / 1e6:.1f} MB")
