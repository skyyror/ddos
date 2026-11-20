#!/data/data/com.termux/files/usr/bin/bash
set -e

# kebutuhan sistem (pakai pkg, bukan apt)
pkg update -y && pkg upgrade -y
pkg install -y git python clang libffi openssl rust

# unduh repo
git clone https://github.com/skyyror/ddos.git
cd REPO

# install dependensi
pip install -r requirements.txt

# jalankan
python ddos.py
