"""Agent registry for contoso-supplier-risk. Add workers here as they scaffold in.

The ``from . import (...)`` block and ``__all__`` list are
scaffold-managed in tuple form; ``scripts/scaffold-agent.py``
inserts new agent ids alphabetically into both. Hand-edits that
collapse this to a single-name import flip the file to "no longer
scaffold-managed" and break ``/add-worker-agent``.
"""
from . import (
    case_drafter,
    evidence_retriever,
    intake_validator,
    risk_scorer,
    supervisor,
)

__all__ = [
    "case_drafter",
    "evidence_retriever",
    "intake_validator",
    "risk_scorer",
    "supervisor",
]
