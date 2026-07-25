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


class ResourceKind(str, Enum):
    USER_MESSAGE = "user_message"
    CONVERSATION = "conversation"
    DOCUMENT = "document"
    MEDICAL_REPORT = "medical_report"
    CALENDAR_EVENT = "calendar_event"
    EMAIL = "email"
    NOTE = "note"
    PROJECT_FILE = "project_file"
    SOURCE_CODE = "source_code"
    TEST_RESULT = "test_result"
    VALIDATION_RESULT = "validation_result"
    UNIVERSITY_RECORD = "university_record"
    OPPOSITION_PLAN = "opposition_plan"
    RELATIONSHIP_EVENT = "relationship_event"
    PERSONAL_PREFERENCE = "personal_preference"
    MEMORY_ENTRY = "memory_entry"
    EXTERNAL_WEB_SOURCE = "external_web_source"
    STRUCTURED_DATASET = "structured_dataset"


class ResourceSourceKind(str, Enum):
    USER_INPUT = "user_input"
    CONVERSATION = "conversation"
    LOCAL_FILE = "local_file"
    UPLOADED_FILE = "uploaded_file"
    CALENDAR = "calendar"
    EMAIL = "email"
    MEMORY = "memory"
    PROJECT = "project"
    VALIDATION_SYSTEM = "validation_system"
    EXTERNAL_WEB = "external_web"
    STRUCTURED_DATA = "structured_data"
    SYSTEM = "system"


class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    HIGHLY_SENSITIVE = "highly_sensitive"
    RESTRICTED = "restricted"


class ResourceIntegrityStatus(str, Enum):
    UNKNOWN = "unknown"
    VERIFIED = "verified"
    MODIFIED = "modified"
    CORRUPTED = "corrupted"
    UNAVAILABLE = "unavailable"


class ResourcePermissionOperation(str, Enum):
    READ = "read"
    INFER = "infer"
    PERSIST = "persist"
    EXPORT = "export"
    TRANSFORM = "transform"
    RELATE = "relate"


class AdaptationStatus(str, Enum):
    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    PARTIAL = "partial"


class ExtractionStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    EMPTY = "empty"


class CandidateKind(str, Enum):
    STATEMENT = "statement"
    ENTITY_MENTION = "entity_mention"
    RELATIONSHIP_MENTION = "relationship_mention"
    TEMPORAL_REFERENCE = "temporal_reference"
    QUANTITY = "quantity"
    KEYWORD = "keyword"
    QUESTION = "question"
    UNKNOWN = "unknown"


# ── Phase 8.4 – Knowledge Model ───────────────────────────────────────────────


class KnowledgeKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    OPINION = "opinion"
    OBSERVATION = "observation"
    DECISION = "decision"
    QUESTION = "question"


class KnowledgeStatus(str, Enum):
    ACTIVE = "active"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class TemporalScopeKind(str, Enum):
    TIMELESS = "timeless"
    CURRENT = "current"
    INTERVAL = "interval"
    POINT_IN_TIME = "point_in_time"
    UNKNOWN = "unknown"


class KnowledgeRelationKind(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    REFINES = "refines"
    SUPERSEDES = "supersedes"
    EQUIVALENT_TO = "equivalent_to"
    RELATED_TO = "related_to"
    ANSWERS = "answers"
    RAISES_QUESTION = "raises_question"


class EvidenceKind(str, Enum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    STATISTICAL = "statistical"
    ANECDOTAL = "anecdotal"
    EXPERT_OPINION = "expert_opinion"
    LOGICAL_INFERENCE = "logical_inference"
    DOCUMENT_REFERENCE = "document_reference"
    EXTRACTION_CANDIDATE = "extraction_candidate"
    UNKNOWN = "unknown"


class EvidencePolarityKind(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


class ContradictionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContradictionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    ACKNOWLEDGED = "acknowledged"
