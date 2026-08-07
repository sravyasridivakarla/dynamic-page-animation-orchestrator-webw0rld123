"""Domain exceptions for page config drafter."""


class ConfigNotFoundError(Exception):
    def __init__(self, config_id):
        self.detail = f"Page config {config_id} not found"
        super().__init__(self.detail)


class KnowledgeGraphUnavailableError(Exception):
    def __init__(self, detail: str = "Knowledge Graph Service is unavailable"):
        self.detail = detail
        super().__init__(self.detail)


class ProvenanceStoreUnavailableError(Exception):
    def __init__(self, detail: str = "Provenance Store is unavailable"):
        self.detail = detail
        super().__init__(self.detail)


class InvalidDraftStateError(Exception):
    def __init__(self, detail: str = "Draft is not in DRAFT_PENDING state"):
        self.detail = detail
        super().__init__(self.detail)


class ParentNotFoundError(Exception):
    def __init__(self, detail: str = "Parent config does not exist"):
        self.detail = detail
        super().__init__(self.detail)


class InvalidEventTypeError(Exception):
    def __init__(self, event_type: str):
        self.detail = f"Event type '{event_type}' is not registered in the Knowledge Graph"
        super().__init__(self.detail)
