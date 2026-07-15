#!/usr/bin/env bash

set -e

echo "=================================="
echo "       CMM OS Doctor v0.1"
echo "=================================="
echo

check() {
    if "$@" >/dev/null 2>&1; then
        echo "✅ $1"
    else
        echo "❌ $1"
    fi
}

echo "[Core]"

check git --version
check docker --version
check ollama --version
check rg --version

echo
echo "[Containers]"

if docker ps --format '{{.Names}}' | grep -q '^n8n$'; then
    echo "✅ n8n"
else
    echo "❌ n8n"
fi

if docker ps --format '{{.Names}}' | grep -q '^open-webui$'; then
    echo "✅ open-webui"
else
    echo "❌ open-webui"
fi

echo
echo "[Models]"

ollama list

echo
echo "Doctor completed."
