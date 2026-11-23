"""Tiny allowlist proxy. Everything else is refused, including the sandbox's own tools."""

import contextlib
import select
import socket
import threading
from urllib.parse import urlsplit

ALLOW = {
    "pypi.org",
    "files.pythonhosted.org",
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
    "api.osv.dev",
    "osv.dev",
    "storage.googleapis.com",
    "pypi.python.org",
}


def _allowed(host: str) -> bool:
    host = host.split(":")[0].lower()
    return host in ALLOW


def _relay(left: socket.socket, right: socket.socket) -> None:
    pair = [left, right]
    try:
        while True:
            readable, _, _ = select.select(pair, [], [], 30)
            if not readable:
                break
            for sock in readable:
                data = sock.recv(65536)
                if not data:
                    return
                other = right if sock is left else left
                other.sendall(data)
    finally:
        left.close()
        right.close()


def _refuse(client: socket.socket, status: bytes) -> None:
    with contextlib.suppress(Exception):
        client.sendall(status)
    with contextlib.suppress(Exception):
        client.close()


def _handle(client: socket.socket) -> None:
    client.settimeout(20)
    try:
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                _refuse(client, b"")
                return
            data += chunk
        line = data.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
        parts = line.split(" ")
        if len(parts) < 2:
            _refuse(client, b"HTTP/1.1 400 bad request\r\nConnection: close\r\n\r\n")
            return
        method, target = parts[0], parts[1]
        if method == "CONNECT":
            host, _, port = target.partition(":")
            if not _allowed(host):
                _refuse(client, b"HTTP/1.1 403 egress denied\r\nConnection: close\r\n\r\n")
                return
            remote = socket.create_connection((host, int(port or "443")), timeout=10)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            _relay(client, remote)
            return
        split = urlsplit(target)
        host = split.hostname or ""
        if not _allowed(host):
            _refuse(client, b"HTTP/1.1 403 egress denied\r\nConnection: close\r\n\r\n")
            return
        port = split.port or (443 if split.scheme == "https" else 80)
        remote = socket.create_connection((host, port), timeout=10)
        remote.sendall(data)
        _relay(client, remote)
    except Exception:
        _refuse(client, b"HTTP/1.1 502 bad gateway\r\nConnection: close\r\n\r\n")


def main() -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 3128))
    server.listen(32)
    while True:
        client, _ = server.accept()
        threading.Thread(target=_handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
