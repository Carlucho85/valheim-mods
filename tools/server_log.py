"""Print a filtered tail of the server BepInEx log. Usage: python tools/server_log.py [regex] [lines]"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sftp_recon

pattern = re.compile(sys.argv[1] if len(sys.argv) > 1 else r"(?i)error|exception|warning|loaded|connected|fail")
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 60
transport, sftp = sftp_recon.connect()
try:
    path = "steamcmd/valheim/BepInEx/LogOutput.log"
    print(sftp.stat(path).st_mtime, sftp.stat(path).st_size)
    with sftp.open(path) as handle:
        lines = handle.read().decode("utf-8", "replace").splitlines()
finally:
    sftp.close()
    transport.close()
print(f"{len(lines)} lines")
hits = [line for line in lines if pattern.search(line)]
for line in hits[-limit:]:
    print(line[:220])
