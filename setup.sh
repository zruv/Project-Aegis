#!/bin/bash
set -e

echo ">>> 🛡️  Project Aegis Setup 🛡️ <<<"

echo "[1/3] Installing Host Python Dependencies..."
sudo python3 -m pip install -r host/requirements.txt

echo "[2/3] Building Vault Docker Image..."
docker build -t aegis-vault ./vault

echo "[3/3] Creating Data Directory..."
mkdir -p host/aegis_data

echo ">>> Setup Complete! <<<"
echo "To flash firmware: cd firmware && pio run --target upload"
echo "To start the system: sudo python3 host/watcher.py"
