"""Read-only SFTP reconnaissance. Credentials come from the local secrets file and are never printed."""
import stat
import sys
from pathlib import Path

import paramiko

SECRETS = Path(r"C:\Users\Carlucho\Documents\akh-secrets\sftp.env")


def load():
    values = {}
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def connect():
    cfg = load()
    transport = paramiko.Transport((cfg["SFTP_HOST"], int(cfg.get("SFTP_PORT", "22"))))
    transport.connect(username=cfg["SFTP_USER"], password=cfg["SFTP_PASSWORD"])
    return transport, paramiko.SFTPClient.from_transport(transport)


def walk(sftp, path, depth, max_depth, out):
    for entry in sorted(sftp.listdir_attr(path), key=lambda e: e.filename):
        full = path.rstrip("/") + "/" + entry.filename
        is_dir = stat.S_ISDIR(entry.st_mode)
        out.append(f"{'D' if is_dir else 'F'} {entry.st_size:>12} {full}")
        if is_dir and depth < max_depth:
            walk(sftp, full, depth + 1, max_depth, out)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    transport, sftp = connect()
    try:
        lines = []
        walk(sftp, root, 0, depth, lines)
        print("\n".join(lines))
    finally:
        sftp.close()
        transport.close()
