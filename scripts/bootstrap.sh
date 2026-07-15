#!/usr/bin/env bash

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=================================="
echo "      CMM OS Bootstrap v0.1"
echo "=================================="
echo

echo "[1/7] Creating project structure..."

mkdir -p "$ROOT/agents/cmm-agent"
mkdir -p "$ROOT/backups"
mkdir -p "$ROOT/config/profiles"
mkdir -p "$ROOT/config/tasks"
mkdir -p "$ROOT/docs"
mkdir -p "$ROOT/memory"
mkdir -p "$ROOT/prompts/shared"
mkdir -p "$ROOT/prompts/system"
mkdir -p "$ROOT/prompts/tasks"
mkdir -p "$ROOT/runtime/n8n"
mkdir -p "$ROOT/schemas"
mkdir -p "$ROOT/scripts"
mkdir -p "$ROOT/services"
mkdir -p "$ROOT/workflows"

echo "✓ Structure ready"

echo
echo "[2/7] Checking Git..."

if command -v git >/dev/null 2>&1; then
    echo "✓ Git: $(git --version)"
else
    echo "✗ Git not found"
fi

echo
echo "[3/7] Checking Docker..."

if command -v docker >/dev/null 2>&1; then
    echo "✓ Docker installed"
else
    echo "✗ Docker not found"
fi

echo
echo "[4/7] Checking Ollama..."

if command -v ollama >/dev/null 2>&1; then
    echo "✓ Ollama: $(ollama --version)"
else
    echo "✗ Ollama not found"
fi

echo
echo "[5/7] Checking Homebrew..."

if command -v brew >/dev/null 2>&1; then
    echo "✓ Homebrew: $(brew --version | head -n1)"
else
    echo "✗ Homebrew not found"
fi

echo
echo "[6/7] Checking ripgrep..."

if command -v rg >/dev/null 2>&1; then
    echo "✓ ripgrep: $(rg --version | head -n1)"
else
    echo "✗ ripgrep not found"
fi

echo
echo "[7/7] Bootstrap complete."

echo
echo "Project root:"
echo "$ROOT"

echo
echo "✅ CMM OS is ready."
