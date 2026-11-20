#!/bin/bash
set -e

# install kebutuhan sistem
apt update && apt install -y git python3 python3-pip python3-venv

# unduh repo
git clone https://github.com/skyyror/ddos
cd REPO

# buat venv & install dependensi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# jalankan file utama
python3 ddos.py
