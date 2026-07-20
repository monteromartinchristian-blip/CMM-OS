# Semantic Python Engine

## Objetivo

El Semantic Python Engine resuelve el problema de modificar código Python de forma segura y semántica. En lugar de editar texto libremente, analiza el código, identifica estructuras relevantes y aplica transformaciones basadas en el árbol sintáctico abstracto (AST).

Esto reduce el riesgo de romper el archivo y permite realizar cambios más precisos, como insertar métodos, renombrarlos o gestionar imports.

## Componentes

### PythonLocator

Responsable de localizar clases, métodos y otras estructuras dentro de un archivo Python.

### PythonTransformer

Implementa las transformaciones semánticas reales sobre el AST, como crear clases, reemplazar clases, insertar o eliminar métodos y gestionar imports.

### PythonEditor

Actúa como la interfaz pública del motor. Expone operaciones de alto nivel que utilizan al transformador para modificar el código de forma controlada.

### PythonValidator

Valida que el resultado de la transformación siga siendo un código Python válido antes de escribir el archivo.

## Flujo interno

```text
source code

↓

AST

↓

semantic transformation

↓

validation

↓

updated source
```

## Operaciones soportadas

- create_class
- replace_class
- insert_method
- replace_method
- rename_method
- delete_method
- ensure_import
- remove_import
- has_import

## Filosofía

Todas las transformaciones se realizan mediante AST y no mediante edición textual porque el AST ofrece una representación estructural del código.

Esto permite:

- preservar la sintaxis correcta del archivo,
- reducir los errores provocados por cambios de texto mal colocados,
- trabajar con elementos semánticos reales como clases, métodos e imports,
- facilitar validaciones y futuras refactorizaciones.

La edición textual es útil para tareas simples, pero resulta frágil cuando el cambio debe ser preciso y seguro.

## Limitaciones actuales

- El motor está enfocado en operaciones básicas de edición semántica.
- No cubre aún todos los casos complejos de refactorización avanzada.
- La validación es suficiente para el alcance de la fase 1, pero puede ampliarse en fases posteriores.

## Futuras mejoras

- Soporte para operaciones más complejas de refactorización.
- Mejor detección de contextos ambiguos.
- Integración más profunda con el planner y el execution engine.
- Mayor seguridad y validación antes de aplicar cambios.
