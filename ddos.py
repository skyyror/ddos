#!/usr/bin/env python3
# language: Python 3, file: ddos.py, runtime: Termux / Linux
# entry point — pastikan core/ ada di path.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.engine import main
except ImportError as e:
    print(f"[!] gagal muat core/: {e}")
    print("    pastikan folder core/ ada di samping ddos.py")
    sys.exit(1)

if __name__ == "__main__":
    main()