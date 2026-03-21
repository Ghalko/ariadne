from __future__ import annotations

from enum import Enum


class FileLanguage(str, Enum):
    python = "python"
    typescript = "typescript"
    javascript = "javascript"
    markdown = "markdown"
    json = "json"
    yaml = "yaml"
    toml = "toml"
    unknown = "unknown"


class NodeKind(str, Enum):
    repo = "repo"
    file = "file"
    symbol = "symbol"
    memory = "memory"
    doc = "doc"
    subsystem = "subsystem"


class MemoryType(str, Enum):
    decision = "decision"
    convention = "convention"
    incident_learning = "incident_learning"
    failed_attempt = "failed_attempt"
    design_note = "design_note"
    constraint = "constraint"
    runbook_note = "runbook_note"


class MemoryStatus(str, Enum):
    active = "active"
    stale = "stale"
    superseded = "superseded"
    deprecated = "deprecated"


class MemorySource(str, Enum):
    manual = "manual"
    imported = "imported"
    generated = "generated"


class EdgeType(str, Enum):
    file_contains_symbol = "FILE_CONTAINS_SYMBOL"
    symbol_calls_symbol = "SYMBOL_CALLS_SYMBOL"
    file_imports_file = "FILE_IMPORTS_FILE"
    symbol_references_symbol = "SYMBOL_REFERENCES_SYMBOL"
    test_covers_symbol = "TEST_COVERS_SYMBOL"
    config_affects_file = "CONFIG_AFFECTS_FILE"
    doc_describes_symbol = "DOC_DESCRIBES_SYMBOL"
    symbol_uses_schema = "SYMBOL_USES_SCHEMA"
    symbol_emits_event = "SYMBOL_EMITS_EVENT"
    symbol_handles_event = "SYMBOL_HANDLES_EVENT"
    applies_to = "APPLIES_TO"
    relates_to = "RELATES_TO"
    supersedes = "SUPERSEDES"
    caused_by = "CAUSED_BY"
    implemented_by = "IMPLEMENTED_BY"
    constrains = "CONSTRAINS"
    warns_about = "WARNS_ABOUT"
