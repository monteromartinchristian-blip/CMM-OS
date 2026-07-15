# CMM Agent v0.1

## Objetivo

CMM Agent es el agente inteligente de CMM OS.

Su función es transformar objetivos de alto nivel en planes de ejecución utilizando los servicios del Kernel.

El agente no implementa lógica de negocio propia.
Toda interacción con el sistema se realiza mediante el Kernel.

---

## Responsabilidades

- Comprender el objetivo del usuario.
- Elaborar un plan.
- Seleccionar herramientas del Kernel.
- Ejecutar acciones paso a paso.
- Solicitar aprobación cuando sea necesario.
- Mantener el contexto de la sesión.

---

## Componentes

- Planner
- Executor
- Tool Registry
- Context Manager
- Session Manager

---

## Principios

- El agente nunca accede directamente a archivos del sistema.
- El agente nunca conoce detalles de proveedores (Ollama, OpenAI, Claude...).
- Toda operación pasa por el Kernel.
- El Kernel es la única interfaz estable del sistema.

---

## Contrato

### Entrada

```json
{
  "goal": "Implementar Prompt Manager",
  "context": {
    "project": "CMM OS"
  }
}
iMac-de-Christian:~ christian$ cat ~/CMM-OS/docs/agent-cmm-v0.1.md
# CMM Agent v0.1

## Objetivo

CMM Agent es el agente inteligente de CMM OS.

Su función es transformar objetivos de alto nivel en planes de ejecución utilizando los servicios del Kernel.

El agente no implementa lógica de negocio propia.
Toda interacción con el sistema se realiza mediante el Kernel.

---

## Responsabilidades

- Comprender el objetivo del usuario.
- Elaborar un plan.
- Seleccionar herramientas del Kernel.
- Ejecutar acciones paso a paso.
- Solicitar aprobación cuando sea necesario.
- Mantener el contexto de la sesión.

---

## Componentes

- Planner
- Executor
- Tool Registry
- Context Manager
- Session Manager

---

## Principios

- El agente nunca accede directamente a archivos del sistema.
- El agente nunca conoce detalles de proveedores (Ollama, OpenAI, Claude...).
- Toda operación pasa por el Kernel.
- El Kernel es la única interfaz estable del sistema.
iMac-de-Christian:~ christian$ cat >> ~/CMM-OS/docs/agent-cmm-v0.1.md << 'EOF'
> 
> ---
> 
> ## Contrato
> 
> ### Entrada
> 
> ```json
> {
>   "goal": "Implementar Prompt Manager",
>   "context": {
>     "project": "CMM OS"
>   }
> }

### Respuesta

```json
{
  "status": "planning",
  "plan": [
    {
      "step": 1,
      "action": "Analizar objetivo"
    },
    {
      "step": 2,
      "action": "Identificar componentes"
    },
    {
      "step": 3,
      "action": "Generar plan de implementación"
    }
  ]
}
```

