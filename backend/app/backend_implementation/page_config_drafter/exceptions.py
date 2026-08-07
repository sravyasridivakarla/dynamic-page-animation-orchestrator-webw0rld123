"""Domain exceptions for the page config drafter feature."""


class ConfigNotFoundError(Exception):
    """Raised when a page config record is not found (HTTP 404)."""

    http_status = 404


class KnowledgeGraphUnavailableError(Exception):
    """Raised when the Knowledge Graph Service is unreachable (HTTP 503)."""

    http_status = 503


class ProvenanceStoreUnavailableError(Exception):
    """Raised when the Provenance & Trace Store is unreachable (HTTP 503)."""

    http_status = 503


class InvalidDraftStateError(Exception):
    """Raised when draft workflow_state is not DRAFT_PENDING (HTTP 400)."""

    http_status = 400


class ParentNotFoundError(Exception):
    """Raised when parent config does not exist and is not being created (HTTP 400)."""

    http_status = 400


class InvalidEventTypeError(Exception):
    """Raised when a sourcing timeline event type is not registered in KG (HTTP 400)."""

    http_status = 400
