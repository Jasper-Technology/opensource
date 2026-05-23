"""
Process-data imports for Jasper.

R1 supports:
- Excel template (``excel.py``)
- DWSIM .dwxml (``dwsim_xml.py``)

R2+ adds Aspen .inp / .rep / HYSYS .hsc / plain-English → LLM template.

Every parser returns an ``ImportResult`` with the Jasper-shaped block +
stream list plus a list of ``Diagnostic`` entries the UI surfaces in the
Diagnostics tab.
"""
from .models import Diagnostic, ImportResult, ImportedBlock, ImportedStream
from .excel import parse_excel
from .dwsim import parse_dwxml
from .describe import describe_to_project
from .aspen_inp import parse_aspen_inp
from .aspen_report import parse_aspen_report

__all__ = [
    "Diagnostic",
    "ImportResult",
    "ImportedBlock",
    "ImportedStream",
    "parse_excel",
    "parse_dwxml",
    "describe_to_project",
    "parse_aspen_inp",
    "parse_aspen_report",
]
