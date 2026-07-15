#!/usr/bin/env bash

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

QUESTION="$*"

if [ -z "$QUESTION" ]; then
    echo "Uso:"
    echo '  ./scripts/agent.sh "¿Qué componentes faltan?"'
    exit 1
fi

echo "Loading registry..."

CONTEXT=""

for file in "$ROOT"/registry/components/*.json
do
    [ -f "$file" ] || continue

    ID=$(grep '"id"' "$file" | sed 's/.*"id": "\(.*\)".*/\1/')
    NAME=$(grep '"name"' "$file" | sed 's/.*"name": "\(.*\)".*/\1/')
    STATUS=$(grep '"status"' "$file" | sed 's/.*"status": "\(.*\)".*/\1/')

    CONTEXT="${CONTEXT}${ID} - ${NAME} - ${STATUS}\n"
done

PROMPT="You are the CMM OS Agent.

Project components:

${CONTEXT}

User request:
${QUESTION}

Answer based only on the project information."

echo
echo "Thinking..."
echo

ollama run qwen2.5-coder:7b "$PROMPT"
