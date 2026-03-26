"""Trace data model — the append-only record of a single agent run.

CRITICAL: This schema is append-only. Fields are NEVER removed or renamed.
New optional fields may be added with a default. Bump TRACE_SCHEMA_VERSION
when adding fields. Never change the meaning of an existing field.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

TRACE_SCHEMA_VERSION = 7


class ToolCallKind(StrEnum):
    """Classify what kind of backend a tool call targeted."""

    DATABASE = "database"
    HTTP_API = "http_api"
    EMAIL = "email"
    FILESYSTEM = "filesystem"
    QUEUE = "queue"
    UNKNOWN = "unknown"


class TraceEventKind(StrEnum):
    """Represent the type of event recorded in a trace."""

    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    APPROVAL = "approval"
    SCENARIO_START = "scenario_start"
    SCENARIO_END = "scenario_end"


class TraceStatus(StrEnum):
    """Describe the overall outcome of one trace."""

    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class ToolCallEvent(BaseModel):
    """Capture one outbound tool call made by the agent."""

    kind: ToolCallKind
    method: str = Field(description="HTTP method or SQL verb")
    target: str = Field(description="URL, table name, or address")
    payload: dict[str, Any] = Field(default_factory=dict)
    response_status: int | None = None
    response_body: dict[str, Any] | None = None
    duration_ms: float | None = None


class LLMRequestEvent(BaseModel):
    """Capture one model request without storing raw prompt text."""

    model: str
    prompt_hash: str = Field(description="SHA-256 of the full prompt")
    token_count_estimate: int | None = None


class LLMResponseEvent(BaseModel):
    """Capture one model response summary."""

    model: str
    output_tokens: int
    finish_reason: str


class ApprovalEvent(BaseModel):
    """Capture one approval signal attached to the scenario or runtime."""

    approval_id: str
    actor: str
    granted: bool = True


class TraceEvent(BaseModel):
    """Represent one timestamped event in the trace timeline."""

    event_id: str
    kind: TraceEventKind
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)
    parent_event_id: str | None = None
    tool_call: ToolCallEvent | None = None
    llm_request: LLMRequestEvent | None = None
    llm_response: LLMResponseEvent | None = None
    approval: ApprovalEvent | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceMetrics(BaseModel):
    """Store aggregate metrics computed from all trace events."""

    total_tool_calls: int = 0
    total_llm_calls: int = 0
    total_tokens_used: int = 0
    total_duration_ms: float = 0.0
    tool_call_breakdown: dict[str, int] = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """Persist the outcome of one policy assertion on the trace."""

    policy_id: str
    evaluator: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class MutationSummary(BaseModel):
    """Summarize mutating tool calls across the run."""

    total_mutations: int = 0
    by_target: dict[str, int] = Field(default_factory=dict)


class DeterminismMetadata(BaseModel):
    """Record replay-related metadata used for deterministic comparison."""

    fixture_hash: str | None = None
    replay_key: str | None = None
    baseline_trace_id: str | None = None


class TraceEvaluation(BaseModel):
    """Persist the final evaluation outcome for one trace."""

    passed: bool
    ase_score: float
    total: int
    passed_count: int
    failed_count: int
    failing_evaluators: list[str] = Field(default_factory=list)


class RuntimeProvenance(BaseModel):
    """Describe which ASE execution path produced the trace."""

    mode: str
    framework: str | None = None
    framework_version: str | None = None
    adapter_name: str | None = None
    adapter_version: str | None = None
    conformance_bundle_version: str | None = None
    event_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterMetadata(BaseModel):
    """Describe the adapter or external runtime that produced the trace."""

    name: str
    transport: str
    framework: str | None = None
    language: str | None = None
    version: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentGraphNode(BaseModel):
    """Represent one node in a multi-agent execution graph."""

    agent_id: str
    name: str | None = None
    role: str | None = None
    parent_agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentGraph(BaseModel):
    """Store graph metadata for multi-agent runs."""

    nodes: list[AgentGraphNode] = Field(default_factory=list)


class SessionTraceEvent(BaseModel):
    """Capture one session read or write checkpoint."""

    session_id: str
    operation: str
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)
    agent_id: str | None = None
    key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffEdge(BaseModel):
    """Capture one delegation edge between two agents."""

    from_agent_id: str
    to_agent_id: str
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalTraceRef(BaseModel):
    """Reference an external trace in another system."""

    system: str
    trace_id: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProtocolEvent(BaseModel):
    """Preserve protocol-level events outside the tool timeline."""

    protocol: str
    event_type: str
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)
    agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceCertificationLevel(StrEnum):
    """Represent the capability tier granted to a certified trace."""

    CORE = "core"
    STATEFUL = "stateful"
    MULTI_AGENT = "multi_agent"
    MCP = "mcp"
    REALTIME = "realtime"


class Trace(BaseModel):
    """Complete record of a single agent scenario run."""

    schema_version: int = TRACE_SCHEMA_VERSION
    trace_id: str
    scenario_id: str
    scenario_name: str
    started_at_ms: float = Field(default_factory=lambda: time.time() * 1000)
    ended_at_ms: float | None = None
    status: TraceStatus = TraceStatus.RUNNING
    events: list[TraceEvent] = Field(default_factory=list)
    metrics: TraceMetrics = Field(default_factory=TraceMetrics)
    tags: dict[str, str] = Field(default_factory=dict)
    mutation_summary: MutationSummary = Field(default_factory=MutationSummary)
    policy_results: list[PolicyResult] = Field(default_factory=list)
    determinism: DeterminismMetadata = Field(default_factory=DeterminismMetadata)
    evaluation: TraceEvaluation | None = None
    runtime_provenance: RuntimeProvenance | None = None
    adapter_metadata: AdapterMetadata | None = None
    agent_graph: AgentGraph = Field(default_factory=AgentGraph)
    session_events: list[SessionTraceEvent] = Field(default_factory=list)
    handoff_edges: list[HandoffEdge] = Field(default_factory=list)
    external_trace_refs: list[ExternalTraceRef] = Field(default_factory=list)
    protocol_events: list[ProtocolEvent] = Field(default_factory=list)
    certification_level: TraceCertificationLevel | None = None
    error_message: str | None = None
    stderr_output: str | None = None
