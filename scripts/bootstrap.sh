#!/usr/bin/env bash

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=================================="
echo "      CMM OS Bootstrap v0.1"
echo "=================================="
echo

echo "[1/9] Creating project structure..."

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
echo "[2/9] Checking Python..."

if command -v python3 >/dev/null 2>&1; then
    echo "✓ Python: $(python3 --version)"
else
    echo "✗ Python not found"
    exit 1
fi

echo
echo "[3/9] Checking Git..."

if command -v git >/dev/null 2>&1; then
    echo "✓ Git: $(git --version)"
else
    echo "✗ Git not found"
    exit 1
fi

echo
echo "[4/9] Checking Ollama..."

if command -v ollama >/dev/null 2>&1; then
    echo "✓ Ollama: $(ollama --version)"
else
    echo "⚠ Ollama not found (optional)"
fi

echo
echo "[5/9] Checking Homebrew..."

if command -v brew >/dev/null 2>&1; then
    echo "✓ Homebrew: $(brew --version | head -n1)"
else
    echo "⚠ Homebrew not found"
fi

echo
echo "[6/9] Checking ripgrep..."

if command -v rg >/dev/null 2>&1; then
    echo "✓ ripgrep: $(rg --version | head -n1)"
else
    echo "⚠ ripgrep not found"
fi

echo
echo "[7/9] Creating virtual environment..."

if [ ! -d "$ROOT/.venv" ]; then
    python3 -m venv "$ROOT/.venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo
echo "[8/9] Installing Python dependencies..."

source "$ROOT/.venv/bin/activate"

python -m pip install --upgrade pip

pip install -r "$ROOT/requirements.txt"

echo "✓ Dependencies installed"

echo
echo "[9/9] Validating CMM OS..."

python -m py_compile "$ROOT/kernel/kernel.py"

echo "✓ Kernel compiled successfully"

echo
echo "=================================="
echo "      CMM OS is ready."
echo "=================================="
echo
echo "Project root:"
echo "$ROOT"
echo
echo "Activate the environment with:"
echo
echo "source .venv/bin/activate"
echo