# API Contract Specification

Create `api_contract.json` (OpenAPI 3.0 subset) at repo root immediately after implementing routes.

## Format
```json
{
  "openapi": "3.0.0",
  "info": { "title": "Service API" },
  "servers": [{ "url": "http://localhost:8000" }],
  "paths": { ... },
  "components": { "schemas": { ... } }
}
```

## Rules
1. Include EVERY route and EVERY schema
2. Type mapping: str->"string", int->"integer", UUID->"string"+"format:uuid", datetime->"string"+"format:date-time"
3. Use `$ref` for request/response bodies
4. `servers[0].url` must match actual listen address (frontend reads this)
5. Count route handlers vs contract entries — must match
