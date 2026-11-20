# language: Python 3, file: core/net.py
# utilitas socket/TLS/checksum dipakai semua worker
import socket, ssl, struct, time

def resolve(host):
    """A record dulu, fallback AAAA. Return list IP unik."""
    try:
        return list({i[4][0] for i in socket.getaddrinfo(host, None, socket.AF_INET)})
    except Exception:
        try:
            return list({i[4][0] for i in socket.getaddrinfo(host, None, socket.AF_INET6)})
        except Exception:
            return []

def konek(ip, port, timeout=3.0, tries=2):
    last = None
    for i in range(tries):
        try:
            return socket.create_connection((ip, port), timeout=timeout)
        except Exception as e:
            last = e
            time.sleep(0.05 * (i + 1))
    raise last if last else ConnectionError("gagal")

def tls_ctx(alpn=None):
    c = ssl._create_unverified_context()
    if alpn:
        try: c.set_alpn_protocols(alpn)
        except Exception: pass
    return c

def checksum(data):
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF

def parse_url(s):
    from urllib.parse import urlparse
    s = s.strip()
    if "://" not in s:
        if ":" in s:
            h, p = s.rsplit(":", 1)
            if p.isdigit():
                return h, int(p), int(p) == 443, "/"
        return s, 80, False, "/"
    p = urlparse(s)
    host = p.hostname or p.netloc
    tls = p.scheme == "https"
    port = p.port or (443 if tls else 80)
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    return host, port, tls, path

def load_lines(path):
    if not path:
        return []
    import os
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out

def load_proxies(path):
    out = []
    for line in load_lines(path):
        if ":" in line:
            h, p = line.rsplit(":", 1)
            try:
                out.append((h, int(p)))
            except Exception:
                pass
    return out