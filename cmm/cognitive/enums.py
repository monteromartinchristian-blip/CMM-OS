from __future__ import annotations

from enum import Enum


class CognitiveStatus(str, Enum):
    PENDING = "pending"
    LOADING_RESOURCES = "loading_resources"
    EXTRACTING_KNOWLEDGE = "extracting_knowledge"
    REASONING = "reasoning"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class CognitiveSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CognitiveActorKind(str, Enum):
    USER = "user"
    SYSTEM = "system"
    MODEL = "model"
    AGENT = "agent"
    WORKFLOW = "workflow"
    EXTERNAL_SOURCE = "external_source"
    HUMAN_REVIEWER = "human_reviewer"
