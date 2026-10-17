"""Restart the Valheim server through the Indifferent Broccoli dashboard.

Replays the request saved by the user in the local secrets folder. Nothing
secret is printed. A real restart only happens with --confirm.
"""
import re
import shlex
import sys
from pathlib import Path

import urllib.request

CURL_FILE = Path(r"C:\Users\Carlucho\Documents\akh-secrets\restart.curl.txt")
BASE = "https://dashboard.indifferentbroccoli.com"


def load():
    command = CURL_FILE.read_text(encoding="utf-8")
    command = command.replace("\\\r\n", " ").replace("\\\n", " ")
    command = re.sub(r"\^\s*\r?\n", " ", command)
    tokens = [token for token in shlex.split(command, posix=True) if token != "^"]
    url_index = next(
        (index for index, token in enumerate(tokens) if token.startswith(("http://", "https://"))),
        None,
    )
    if url_index is None:
        raise ValueError(
            "restart.curl.txt must contain the copied cURL request, not the JSON response."
        )
    url, data, cookie = tokens[url_index], None, None
    headers = {}
    i = url_index + 1
    while i < len(tokens):
        tok = tokens[i].lstrip("^")
        if tok in ("-b", "--cookie"):
            cookie = tokens[i + 1]; i += 2
        elif tok in ("-H", "--header"):
            name, _, value = tokens[i + 1].partition(":")
            name = name.strip().lstrip("^")
            if name.strip().lower() == "cookie":
                cookie = value.strip()
            elif not name.lower().startswith("sec-"):
                headers[name.strip()] = value.strip()
            i += 2
        elif tok in ("--data-raw", "--data", "-d"):
            data = tokens[i + 1]; i += 2
        else:
            i += 1
    if cookie:
        headers["Cookie"] = cookie
    return url, data, headers


def session_valid(headers):
    req = urllib.request.Request(BASE + "/", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return "/login" not in resp.geturl(), resp.geturl()


def restart(url, data, headers):
    req = urllib.request.Request(url, data=data.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode(errors="replace")
    return re.search(r'"query"\s*:\s*"([^"]+)"', body), body


if __name__ == "__main__":
    try:
        url, data, headers = load()
    except (OSError, ValueError) as exc:
        sys.exit(f"invalid restart.curl.txt: {exc}")
    valid, final = session_valid(headers)
    print("session valid:", valid)
    if "--confirm" not in sys.argv:
        print("dry run: pass --confirm to restart")
        sys.exit(0 if valid else 1)
    if not valid:
        sys.exit("session expired: refresh restart.curl.txt")
    match, body = restart(url, data, headers)
    print("result:", match.group(1) if match else body[:200])
