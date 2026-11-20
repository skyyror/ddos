# language: Python 3, file: core/config.py
# profil-aware config persistence — tiap profil terpisah di ddos.json
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE, "ddos.json")
LOG_DIR = os.path.join(BASE, "logs")

DEFAULTS = {
    "host": "", "port": 80, "tls": False, "path": "/",
    "method": "http", "threads": 100, "duration": 60,
    "keepalive": False, "size": 1024,
    "payload_mode": "rand",        # rand | json | form
    "proxy_file": "", "ua_file": "", "targets_file": "",
    "stealth": False, "stealth_min_ms": 30, "stealth_max_ms": 300,
    "log_file": "",
    "profile": "default",
}

def _ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)

def load_cfg():
    """Muat profil aktif + merge defaults."""
    cfg = dict(DEFAULTS)
    if not os.path.exists(CONFIG_FILE):
        return cfg
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
    except Exception:
        return cfg
    active = data.get("active", "default")
    profiles = data.get("profiles", {})
    cfg["profile"] = active
    if active in profiles:
        for k in DEFAULTS:
            if k in profiles[active]:
                cfg[k] = profiles[active][k]
    return cfg

def save_cfg(cfg):
    _ensure_dirs()
    active = cfg.get("profile", "default")
    profiles = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                profiles = json.load(f).get("profiles", {})
        except Exception:
            profiles = {}
    profiles[active] = {k: v for k, v in cfg.items() if k != "profile"}
    payload = {"active": active, "profiles": profiles}
    with open(CONFIG_FILE, "w") as f:
        json.dump(payload, f, indent=2)

def list_profiles():
    if not os.path.exists(CONFIG_FILE): return ["default"]
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return list(data.get("profiles", {}).keys()) or ["default"]
    except Exception:
        return ["default"]