# Module Conventions

## 6-File Pattern

Every feature gets its own subdirectory under a capability module folder in `backend/app/`:

```
backend/app/<capability_module>/
    <feature_name>/
        __init__.py          # Package init (re-exports)
        models.py            # SQLAlchemy models
        schema.py            # Pydantic request/response schemas
        repository.py        # Data access layer
        service.py           # Business logic
        api.py               # FastAPI router with endpoints
```

The capability module name and feature name come from the task's `code_path` (e.g. `code_path: my_svc/my_feature/` → `backend/app/my_svc/my_feature/`).

| File | Purpose | Example Location |
|------|---------|-----------------|
| `models.py` | SQLAlchemy models | `backend/app/<capability_module>/<feature>/models.py` |
| `schema.py` | Pydantic request/response schemas | `backend/app/<capability_module>/<feature>/schema.py` |
| `repository.py` | Data access layer | `backend/app/<capability_module>/<feature>/repository.py` |
| `service.py` | Business logic | `backend/app/<capability_module>/<feature>/service.py` |
| `api.py` | FastAPI router with endpoints | `backend/app/<capability_module>/<feature>/api.py` |
| `__init__.py` | Package init (re-exports) | `backend/app/<capability_module>/<feature>/__init__.py` |

Each feature lives in its own subdirectory under the capability module. Files use **short names** (`models.py`, `api.py`) — NOT prefixed names like `feature_name_models.py`.

## Naming Conventions

- **Feature folders**: `snake_case` — e.g. `product_page_config/`, `category/`
- **Files**: short role names — `models.py`, `schema.py`, `api.py`, `service.py`, `repository.py`
- **Classes**: `PascalCase` — e.g. `ProductPageConfig` (model), `ProductPageConfigCreate` (schema)
- **Tables**: plural `snake_case` — e.g. `product_page_configs`
- **Routers**: prefix matches resource name (plural) — e.g. `/product-page-configs`
- **Tests**: `test_<feature>_service.py` in `backend/tests/unit/`

## Models (`models.py`)

```python
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ProductPageConfig:
    __tablename__ = "product_page_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

## Schemas (`schema.py`)

```python
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class ProductPageConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class ProductPageConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)

class ProductPageConfigResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    model_config = {{"from_attributes": True}}
```

## Repository (`repository.py`)

```python
class ProductPageConfigRepository:
    def __init__(self, db_session):
        self.db = db_session

    async def find_all(self): ...
    async def find_by_id(self, entity_id): ...
    async def create(self, data): ...
    async def update(self, entity_id, data): ...
    async def delete(self, entity_id): ...
```

## Service (`service.py`)

```python
import structlog
logger = structlog.get_logger()

class ProductPageConfigService:
    def __init__(self, repository):
        self.repository = repository

    async def list_all(self): ...
    async def get_by_id(self, entity_id): ...
    async def create(self, data): ...
    async def update(self, entity_id, data): ...
    async def delete(self, entity_id): ...
```

## API (`api.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/product-page-configs", tags=["product-page-configs"])

@router.get("/")
async def list_items(): ...

@router.get("/{{item_id}}")
async def get_item(item_id): ...

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(data): ...

@router.put("/{{item_id}}")
async def update_item(item_id, data): ...

@router.delete("/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id): ...
```

## Import Pattern

```python
# From within the feature folder (relative imports):
from .models import ProductPageConfig
from .schema import ProductPageConfigCreate, ProductPageConfigResponse
from .repository import ProductPageConfigRepository
from .service import ProductPageConfigService

# From another feature or elsewhere in the app (absolute imports):
from app.<capability_module>.<feature>.models import ProductPageConfig
from app.<capability_module>.<feature>.schema import ProductPageConfigCreate
```

## Running

```bash
# From backend/ directory (or inside Docker container)
uvicorn app.main:app --reload
pytest tests/ -v

# From project root
cd backend && uvicorn app.main:app --reload
cd backend && pytest tests/ -v
```
