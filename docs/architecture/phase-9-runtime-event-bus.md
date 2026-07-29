# Phase 9.20 – Runtime Event Bus

## Objetivo

Construir un bus de eventos estructurado, tipado, auditable y desacoplado para que el Agent Runtime pueda emitir eventos sin depender directamente de UI, observabilidad, n8n, persistencia, otros agentes o futuras integraciones.

## Contratos

- `AgentRuntimeEvent`: evento inmutable
- `AgentRuntimeEventHeader`: metadatos de cabecera
- `AgentRuntimeEventPayload`: datos del evento
- `AgentRuntimeEventEnvelope`: sobre con información de entrega
- `AgentRuntimeEventSubscription`: suscripción
- `AgentRuntimeEventFilter`: filtros
- `AgentRuntimeEventDelivery`: resultado de entrega
- `AgentRuntimeEventBatch`: lote de eventos
- `AgentRuntimeEventDeadLetter`: dead letter
- `AgentRuntimeEventReplayRequest`: solicitud de replay
- `AgentRuntimeEventReplayResult`: resultado de replay
- `AgentRuntimeEventBusStats`: estadísticas

## Familias de eventos

- Goals: `goal.created`, `goal.updated`, etc.
- Runtime: `agent_run.created`, etc.
- Iteraciones: `agent_iteration.started`, etc.
- Observación: `observation.started`, etc.
- Planificación: `workflow_plan.created`, etc.
- Política/aprobación/presupuesto: `policy.evaluated`, etc.
- Ejecución/validación: `operation.started`, etc.
- Recuperación: `recovery.started`, etc.
- Resultado/memoria: `outcome_evaluation.started`, etc.
- Traza/control: `agent_trace.created`, `runtime.error`, etc.

## Correlación y causación

- `correlation_id`: agrupa eventos relacionados
- `causation_id`: identifica el evento que causó este evento
- El normalizador completa `correlation_id` desde `causation_id` si falta

## Registry

- Registro inicial de todos los eventos conocidos
- Aliases
- Validadores opcionales por tipo
- Modo estricto/tolerante
- Prevención de duplicados

## Publicación y suscripción

- `publish`: publicación síncrona inicial
- `publish_many`: publicación en lote
- `subscribe`: suscripción con filtros
- `unsubscribe`: baja de suscripción
- FIFO garantizado
- Aislamiento entre handlers

## Filtros

- Por `event_type`
- Por `agent_id`, `agent_run_id`, `goal_id`, `workflow_id`
- Por `correlation_id`
- Filtros custom en metadata

## Idempotencia

- Control por `event_id`
- Detección de duplicados por `event_id`
- Rechazo de eventos duplicados en modo estricto

## Backpressure

- `max_queue_size` configurable
- `AgentRuntimeEventQueueFullError` cuando se supera

## Delivery

Estados posibles:
- `delivered`
- `skipped`
- `filtered`
- `duplicate`
- `failed`
- `dead_lettered`

## Dead letters

- `InMemoryAgentRuntimeDeadLetterQueue`
- Información de error estructurada
- Número de intentos
- Primer y último fallo
- Replay posible

## Replay

- Por `event_id`, rango temporal, tipo, run_id, goal_id, correlation_id
- Límite configurable
- Orden cronológico
- Dry-run
- Prevención de replay infinito
- Trazabilidad preservada

## Persistencia

- `AgentRuntimeEventRepository`
- `InMemoryAgentRuntimeEventRepository`
- Append-only
- No sobrescritura

## Integración con 9.19

- `AgentTraceEventSubscriber`
- Consume eventos del bus
- Alimenta `AgentTraceCollector` / `AgentTraceService`
- Redacción antes de persistir
- Fallo aislado

## Seguridad

- Sensibilidad: `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`
- Permisos por evento
- Rechazo de `chain-of-thought`
- Rechazo de secretos

## Límites

- Queue máxima configurable
- Tamaño de payload razonable
- Timestamps timezone-aware
- No shell/eval
- No ejecución dinámica arbitraria

## Ejemplos

```python
from cmm.agent_runtime import (
    AgentRuntimeEventBus,
    AgentRuntimeEventFactory,
    AgentRuntimeEventRegistry,
    EventType,
)

bus = AgentRuntimeEventBus()
factory = AgentRuntimeEventFactory()

def handler(event):
    print(event.header.event_type)

sub_id = bus.subscribe(handler, [EventType.GOAL_CREATED])
event = factory.create_event(EventType.GOAL_CREATED, {"goal_id": "g1"}, agent_id="a1")
bus.publish(event)