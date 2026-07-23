FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

WORKDIR /app

# Install runtime deps from pyproject.toml — single source of truth.
# Version pins live in pyproject.toml + ga-versions.yaml and are gated by
# scripts/accelerator-lint.py::sdks_pinned_to_ga. The image therefore ships
# exactly the SDK matrix that CI enforces; drift is impossible.
COPY pyproject.toml README.md ./
COPY src ./src
# accelerator.yaml is the engagement manifest. src.workflow.registry resolves
# ROOT as the image workdir (/app) and loads accelerator.yaml at startup, so
# the runtime image MUST ship it. scripts/accelerator-lint.py::dockerfile_copies_manifest
# enforces this invariant.
COPY accelerator.yaml ./
# docs/agent-specs/<foundry_name>.md hold the Instructions body for every
# scenario.agents[] entry. Bootstrap syncs managed agents; Harness loads the
# same source at runtime. scripts/accelerator-lint.py::dockerfile_copies_agent_specs
# enforces this invariant.
COPY docs/agent-specs ./docs/agent-specs
# data/ holds seed JSON files referenced by scenario.retrieval.indexes[].seed.
# src.bootstrap uploads them at startup so the AI Search index is queryable
# the moment /healthz returns 200.
COPY data ./data
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8000

# Workload-identity friendly: no secrets baked in; env vars come from Container App
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
