#!/bin/sh
set -e

sed -i "s|PLACEHOLDER_OPENROUTER_API_KEY|${OPENROUTER_API_KEY}|g" config.json
sed -i "s|PLACEHOLDER_TELEGRAM_TOKEN|${TELEGRAM_TOKEN}|g" config.json
sed -i "s|PLACEHOLDER_TELEGRAM_USER|${TELEGRAM_USER}|g" config.json

mkdir -p ~/.picoclaw
cp config.json ~/.picoclaw/config.json

echo ""
echo "=============================================="
echo "  PicoClaw Bot Starting..."
echo "=============================================="
echo ""
echo "📋 Configuration:"
echo "   - Model: $(grep -o '"model": *"[^"]*"' config.json | head -1 | cut -d'"' -f4)"
echo "   - Provider: OpenRouter"
echo "   - Channel: Telegram"
echo ""
echo "🤖 Model List (fallback order):"
grep -A 3 '"model_name":' config.json | grep 'model_name\|model"' | while read -r line; do
  name=$(echo "$line" | grep -o '"model_name": *"[^"]*"' | cut -d'"' -f4)
  model=$(grep -A 1 "$name" config.json | grep '"model":' | cut -d'"' -f4)
  if [ -n "$name" ] && [ -n "$model" ]; then
    echo "   • $name → $model"
  fi
done
echo ""
echo "=============================================="
echo ""

echo "[entrypoint] Config ready. Starting gateway..."
exec ./picoclaw gateway
