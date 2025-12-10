#!/bin/bash
set -e

echo ">>> 🩹 Patching 'aegis-vault' Docker Image..."

# 1. Create a temporary container from the existing image
# We use || true to ignore error if image doesn't exist (though it should)
CTR_ID=$(docker create aegis-vault)

if [ -z "$CTR_ID" ]; then
    echo "Error: Could not find image 'aegis-vault'. Please run setup.sh first (even if it fails at the end)."
    exit 1
fi

echo "   -> Container ID: $CTR_ID"

# 2. Inject the updated files
echo "   -> Injecting updated app.py..."
docker cp vault/app.py $CTR_ID:/app/app.py

echo "   -> Injecting updated index.html..."
docker cp vault/templates/index.html $CTR_ID:/app/templates/index.html

# 3. Commit the changes back to the image
echo "   -> Committing changes to image..."
docker commit $CTR_ID aegis-vault

# 4. Clean up
echo "   -> Cleaning up..."
docker rm -v $CTR_ID

echo ">>> ✅ Patch Complete!"
echo "Now run: sudo python3 host/watcher.py"
