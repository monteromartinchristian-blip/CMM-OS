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
