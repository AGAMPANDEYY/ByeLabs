"""
HiLabs Roster Processing - Agent Package

This package contains all the processing agents for the multi-agent pipeline:
- intake_email: Email parsing and initial processing
- classifier: Document type classification
- extract_rule: Rule-based extraction
- extract_pdf: PDF-specific extraction
- vlm_client: Vision Language Model client
- normalizer: Data normalization
- validator: Data validation
- versioner: Version management
- exporter_excel: Excel export generation
"""

from .intake_email import run as intake_email_run
from .classifier import run as classifier_run
from .extract_rule import run as extract_rule_run
from .extract_pdf import run as extract_pdf_run
from .vlm_client import run as vlm_client_run
from .normalizer import run as normalizer_run
from .validator import run as validator_run
from .versioner import run as versioner_run
from .exporter_excel import run as exporter_excel_run

__all__ = [
    "intake_email_run",
    "classifier_run", 
    "extract_rule_run",
    "extract_pdf_run",
    "vlm_client_run",
    "normalizer_run",
    "validator_run",
    "versioner_run",
    "exporter_excel_run"
]
