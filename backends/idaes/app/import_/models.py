"""Shared shapes for all import parsers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class Diagnostic:
    severity: Literal["error", "warning", "info"]
    message: str
    location: Optional[str] = None  # sheet/row/cell reference for UI


@dataclass
class ImportedStream:
    id: str
    from_block: Optional[str]
    from_port: Optional[str]
    to_block: Optional[str]
    to_port: Optional[str]
    T: Optional[float] = None          # K
    P: Optional[float] = None          # Pa
    flow_mol: Optional[float] = None   # mol/s
    flow_mass: Optional[float] = None  # kg/s
    composition: dict[str, float] = field(default_factory=dict)


@dataclass
class ImportedBlock:
    id: str
    type: str
    name: str
    params: dict[str, object] = field(default_factory=dict)
    # Solved operating data supplied by the import (if any)
    duty: Optional[float] = None            # W
    work: Optional[float] = None            # W
    pressure_drop: Optional[float] = None   # Pa


@dataclass
class ImportedProject:
    name: str
    components: list[str]
    blocks: list[ImportedBlock]
    streams: list[ImportedStream]


@dataclass
class ImportResult:
    project: Optional[ImportedProject]
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    def count(self, severity: str) -> int:
        return sum(1 for d in self.diagnostics if d.severity == severity)
