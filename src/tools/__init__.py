"""Tool registry.

Workflow executors import from here so agent wiring is declarative.
"""
from .create_supplier_risk_case import SCHEMA as CREATE_SUPPLIER_RISK_CASE_SCHEMA
from .create_supplier_risk_case import create_supplier_risk_case
from .crm_read import SCHEMA as CRM_READ_SCHEMA
from .crm_read import crm_read_account
from .crm_write_contact import SCHEMA as CRM_WRITE_SCHEMA
from .crm_write_contact import crm_write_contact
from .send_email import SCHEMA as SEND_EMAIL_SCHEMA
from .send_email import send_email
from .update_supplier_review_status import (
    SCHEMA as UPDATE_SUPPLIER_REVIEW_STATUS_SCHEMA,
)
from .update_supplier_review_status import update_supplier_review_status
from .web_search import SCHEMA as WEB_SEARCH_SCHEMA
from .web_search import web_search

READ_ONLY_TOOLS = {
    "crm_read_account": (crm_read_account, CRM_READ_SCHEMA),
    "web_search": (web_search, WEB_SEARCH_SCHEMA),
}

SIDE_EFFECT_TOOLS = {
    # Flagship sales-research scenario (kept available for partners that
    # re-enable the supervisor-routing default).
    "crm_write_contact": (crm_write_contact, CRM_WRITE_SCHEMA),
    "send_email": (send_email, SEND_EMAIL_SCHEMA),
    # contoso-supplier-risk side-effect tools (solution-brief.md Section 5).
    "create_supplier_risk_case": (
        create_supplier_risk_case, CREATE_SUPPLIER_RISK_CASE_SCHEMA,
    ),
    "update_supplier_review_status": (
        update_supplier_review_status, UPDATE_SUPPLIER_REVIEW_STATUS_SCHEMA,
    ),
}

ALL_TOOLS = {**READ_ONLY_TOOLS, **SIDE_EFFECT_TOOLS}
