# KERNEL-003 — Prompt Manager

## Objetivo

Resolver un prompt_id y devolver el contenido completo del prompt.

El Prompt Manager no conoce tareas, modelos ni proveedores.

Su única responsabilidad es cargar prompts registrados.

---

## Entrada

{
  "prompt_id": "summarize"
}

---

## Salida

{
  "prompt_id": "summarize",
  "content": "..."
}

---

## Responsabilidades

- Cargar prompts desde prompts/.
- Validar que el prompt existe.
- Devolver el contenido íntegro.
- No modificar el contenido.
