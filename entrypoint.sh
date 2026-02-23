#!/bin/sh
set -e

sed -i "s|PLACEHOLDER_OPENROUTER_API_KEY|${OPENROUTER_API_KEY}|g" config.json
sed -i "s|PLACEHOLDER_TELEGRAM_TOKEN|${TELEGRAM_TOKEN}|g" config.json
sed -i "s|PLACEHOLDER_TELEGRAM_USER|${TELEGRAM_USER}|g" config.json

mkdir -p ~/.picoclaw
cp config.json ~/.picoclaw/config.json

echo "[entrypoint] Config ready. Starting gateway..."
exec ./picoclaw gateway
