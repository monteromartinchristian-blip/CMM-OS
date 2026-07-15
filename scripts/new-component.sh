#!/usr/bin/env bash

set -e

if [ $# -lt 2 ]; then
    echo "Uso:"
    echo "  ./scripts/new-component.sh <ID> <Nombre>"
    echo
    echo "Ejemplo:"
    echo '  ./scripts/new-component.sh KERNEL-003 "Prompt Manager"'
    exit 1
fi

ID="$1"
NAME="$2"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$ROOT/registry/components"

FILE="$ROOT/registry/components/$ID.json"

if [ -f "$FILE" ]; then
    echo "❌ El componente $ID ya existe."
    exit 1
fi

cat > "$FILE" <<JSON
{
  "id": "$ID",
  "name": "$NAME",
  "type": "unknown",
  "status": "planned",
  "version": "0.1",
  "dependencies": [],
  "description": ""
}
JSON

echo
echo "✅ Componente creado:"
echo "   $FILE"
