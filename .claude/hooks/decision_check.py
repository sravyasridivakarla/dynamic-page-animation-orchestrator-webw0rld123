#!/usr/bin/env python3
"""Generated from the decision registry; do not edit by hand; regenerated on each run.

PostToolUse hook: checks writes against the governing decisions this
repository was generated under. Exit 2 blocks with feedback; anything
else stays silent. Stdlib only, non-fatal on every unexpected path.
"""
import json
import os
import re
import subprocess
import sys

CONFIG = {
  "dependency_allowlist": {
    "cite": "DEC-SEC-9 (Approved Python Dependency Allowlist for Agent Services)",
    "packages": [
      "alembic",
      "fastapi",
      "httpx",
      "pydantic",
      "pytest",
      "python-dotenv",
      "redis",
      "sqlalchemy",
      "structlog",
      "uvicorn"
    ]
  },
  "import_contracts": {
    "api-must-not-import-db": {
      "public_id": "DEC-BAK-48",
      "title": "Layered Module Boundaries for Agent Services"
    }
  }
}

DEP_FILES = ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "package.json")


def _packages_from(path, content):
    base = os.path.basename(path or "")
    pkgs = set()
    if base.startswith("requirements") and base.endswith(".txt"):
        for line in (content or "").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9_.-]+)", line)
            if m:
                pkgs.add(m.group(1).lower())
    elif base == "package.json":
        try:
            data = json.loads(content or "{}")
            for key in ("dependencies", "devDependencies"):
                pkgs.update(k.lower() for k in (data.get(key) or {}))
        except Exception:
            pass
    elif base == "pyproject.toml":
        for m in re.finditer(r'"([A-Za-z0-9_.-]+)[><=~!\[]', content or ""):
            pkgs.add(m.group(1).lower())
    return pkgs


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    base = os.path.basename(path)

    allow = CONFIG.get("dependency_allowlist") or {}
    if allow.get("packages") and base in DEP_FILES:
        try:
            content = open(path, encoding="utf-8").read() if os.path.exists(path) else (
                tool_input.get("content") or tool_input.get("new_string") or ""
            )
            found = _packages_from(path, content)
            blocked = sorted(found - set(allow["packages"]))
            if blocked:
                cite = allow.get("cite") or "a governing technology decision"
                plural = "s" if len(blocked) > 1 else ""
                sys.stderr.write(
                    "Package%s %s %s not on the approved dependency list. "
                    "This repository follows decision %s. Remove %s or use one "
                    "of the approved packages: %s. If none of them fits, "
                    "surface the conflict instead of working around it. See "
                    ".claude/rules/ for the rules this repo was generated under.\n"
                    % (plural, ", ".join(blocked), "are" if plural else "is",
                       cite, ", ".join(blocked), ", ".join(sorted(allow["packages"])))
                )
                return 2
        except Exception:
            return 0

    contracts = CONFIG.get("import_contracts") or {}
    if contracts and path.endswith(".py") and os.path.exists(".importlinter"):
        try:
            r = subprocess.run(
                ["lint-imports", "--config", ".importlinter"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                broken = [
                    line.strip()[: -len(" BROKEN")].strip()
                    for line in (r.stdout or "").splitlines()
                    if line.strip().endswith(" BROKEN")
                ]
                if broken:
                    cites = []
                    for name in broken:
                        meta = contracts.get(name) or {}
                        pid = meta.get("public_id")
                        title = meta.get("title")
                        if pid and title:
                            cites.append("'%s' (decision %s (%s))" % (name, pid, title))
                        else:
                            cites.append("'%s'" % name)
                    plural = "s" if len(broken) > 1 else ""
                    sys.stderr.write(
                        "Import boundary violation in %s. Broken contract%s: %s. "
                        "Remove the import that crosses this boundary and keep "
                        "the modules separate as the contract requires. The "
                        "contracts live in .importlinter, and .claude/rules/ has "
                        "the decisions behind them.\n"
                        % (path, plural, ", ".join(cites))
                    )
                    return 2
        except FileNotFoundError:
            return 0
        except Exception:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
