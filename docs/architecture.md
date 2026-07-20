# Architecture

## Visión general

CMM OS es un sistema operativo orientado a software que busca transformar intenciones humanas en acciones concretas sobre un proyecto de código. Su enfoque principal no es editar archivos de forma directa, sino traducir una intención en un plan estructurado, validado y ejecutado de forma segura.

## Objetivo principal

El objetivo de CMM OS es convertir la intención de desarrollo en acciones verificables y controladas, reduciendo el riesgo de cambios arbitrarios y mejorando la trazabilidad del proceso.

## Componentes principales

### 1. Semantic Planner

Es la capa encargada de interpretar una intención y convertirla en un plan semántico de ejecución. Esta fase define qué debe hacerse antes de modificar el código.

### 2. Execution Plan

Representa la secuencia de acciones a ejecutar. Sirve como puente entre la intención y la ejecución real del cambio.

### 3. Semantic Python Engine

Es la capa de ejecución específica para manipular código Python de forma segura. Usa un modelo basado en AST para aplicar cambios semánticos sin depender de ediciones textuales frágiles.

### 4. Project Files

Son los archivos reales del proyecto que reciben los cambios. El motor actúa sobre ellos de manera controlada y validada.

## Diagrama general

```text
User Intent
      │
      ▼
Semantic Planner
      │
      ▼
Execution Plan
      │
      ▼
Semantic Python Engine
      │
      ▼
Project Files
```

## Descripción de cada bloque

- User Intent: la instrucción o necesidad expresada por el usuario.
- Semantic Planner: transforma esa intención en un plan estructurado.
- Execution Plan: representa las acciones ordenadas que deben ejecutarse.
- Semantic Python Engine: aplica los cambios semánticos sobre el código.
- Project Files: resultado final del proceso sobre el repositorio.

## Cómo interactuarán las futuras fases

Las fases futuras irán ampliando esta arquitectura en capas:

- La fase actual aporta la capacidad de editar código Python de forma semántica.
- La siguiente fase permitirá convertir intenciones más complejas en planes detallados.
- Luego, el motor de ejecución podrá aplicar esos planes de forma más completa.
- Más adelante, la capa de intención permitirá una interacción más natural con LLMs.
- Finalmente, la memoria persistente y la autonomía del sistema permitirán operar de forma más independiente.
