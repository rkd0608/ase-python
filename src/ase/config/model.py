"""Pydantic models for ASE project configuration and CLI output formats."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class OutputFormat(StrEnum):
    """Enumerate stable report/output modes shared by ASE CLI commands."""

    TERMINAL = "terminal"
    JSON = "json"
    JUNIT = "junit"
    MARKDOWN = "markdown"
    OTEL_JSON = "otel-json"


class ProxyConfig(BaseModel):
    """Capture proxy defaults so watch/test can run reproducibly from config."""

    port: int = 0
    bind_address: str = "127.0.0.1"


class CacheConfig(BaseModel):
    """Describe the on-disk response cache used for deterministic test runs."""

    enabled: bool = True
    directory: str = ".ase-cache"
    max_entries: int = 1000


class TraceStoreConfig(BaseModel):
    """Describe where ASE stores local run history and how much to retain."""

    directory: str = ".ase-traces"
    keep_last: int = 100


class ASEConfig(BaseModel):
    """Define the project-level ASE defaults loaded from `ase.yaml`."""

    version: int = 1
    output: OutputFormat = OutputFormat.TERMINAL
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    traces: TraceStoreConfig = Field(default_factory=TraceStoreConfig)
    scenario_dirs: list[str] = Field(default_factory=lambda: ["scenarios"])
    env_files: list[str] = Field(default_factory=list)
