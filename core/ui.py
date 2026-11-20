# language: Python 3, file: core/ui.py
# warna, banner, prompt — semua UI di sini
import os

try:
    import pyfiglet
    _FIG = True
except ImportError:
    _FIG = False

try:
    from rich.console import Console
    _RICH = True
    _con = Console()
except ImportError:
    _RICH = False
    _con = None

class C:
    R="\033[0m"; B="\033[1m"; D="\033[2m"
    G="\033[92m"; Cy="\033[96m"; Y="\033[93m"
    Rd="\033[91m"; Mg="\033[95m"; Bl="\033[94m"

_BANNER = r"""
   ██████╗ ██████╗  ██████╗ ███████╗
   ██╔══██╗██╔══██╗██╔═══██╗██╔════╝
   ██║  ██║██████╔╝██║   ██║███████╗
   ██║  ██║██╔══██╗██║   ██║╚════██║
   ██████╔╝██║  ██║╚██████╔╝███████║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"""

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def banner(subtitle):
    cls()
    if _FIG:
        try:
            print(C.G + C.B + pyfiglet.figlet_format("DDOS", font="slant") + C.R)
        except Exception:
            print(C.G + C.B + _BANNER + C.R)
    else:
        print(C.G + C.B + _BANNER + C.R)
    print(C.Cy + f"    {subtitle}" + C.R)
    print(C.D + "    " + "─" * 48 + C.R)

def h1(text):
    print(C.Cy + C.B + f"\n  ── {text} ──\n" + C.R)

def hr(char="─", w=50):
    print(C.D + "  " + char * w + C.R)

def prompt(text, default=""):
    if default != "" and default is not None:
        v = input(f"  {C.Y}{text}{C.R} {C.D}[{default}]{C.R}: ").strip()
        return v if v else str(default)
    return input(f"  {C.Y}{text}{C.R}: ").strip()

def prompt_int(text, default):
    v = prompt(text, default)
    try: return int(v)
    except: return default

def prompt_bool(text, default=False):
    d = "y" if default else "n"
    v = prompt(f"{text} y/n", d).lower()
    return v in ("y", "yes", "1", "true", "on")

def wait(msg="enter…"):
    input(f"  {C.D}{msg}{C.R}")

def info(k, v):
    print(f"  {C.D}{k:<10}{C.R} {C.G}{v}{C.R}")

def ok(msg):    print(f"  {C.G}»  {msg}{C.R}")
def warn(msg):  print(f"  {C.Y}[!] {msg}{C.R}")
def fail(msg):  print(f"  {C.Rd}[!] {msg}{C.R}")