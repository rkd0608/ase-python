"""Scenario configuration models consumed by the ASE runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ase.conformance.model import CertificationLevel

SCENARIO_SPEC_VERSION = 1
DEFAULT_BASELINE_METRICS = [
    "total_tool_calls",
    "total_llm_calls",
    "total_tokens_used",
]


class EnvironmentKind(StrEnum):
    """Which backend mode a scenario uses."""

    REAL = "real"
    MOCK = "mock"
    SIMULATED = "simulated"


class AgentRuntimeMode(StrEnum):
    """Which ASE runtime path executes the scenario."""

    PROXY = "proxy"
    INSTRUMENTED = "instrumented"
    ADAPTER = "adapter"


class AdapterTransport(StrEnum):
    """How adapter events are delivered into ASE."""

    JSONL_STDIO = "jsonl-stdio"
    HTTP = "http"


class BaselineMode(StrEnum):
    """How baseline comparison should behave."""

    TOOL_CALLS = "tool_calls"
    METRICS = "metrics"
    COMBINED = "combined"


class AgentConfig(BaseModel):
    """How ASE launches the agent subprocess."""

    command: list[str] = Field(description="Shell command to run the agent")
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=1)


class AgentRuntimeConfig(BaseModel):
    """Describe the runtime and methodology of the agent under test."""

    mode: AgentRuntimeMode | None = None
    framework: str | None = None
    language: str | None = None
    version: str | None = None
    methodology: str | None = None
    entrypoint: str | None = None
    adapter_name: str | None = None
    event_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterConfig(BaseModel):
    """Declare how a non-proxy runtime integrates with ASE."""

    name: str
    transport: AdapterTransport = AdapterTransport.JSONL_STDIO
    command: list[str] = Field(default_factory=list)
    url: str | None = None
    timeout_seconds: int = Field(default=60, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalFixture(BaseModel):
    """Declare one approval available during the run."""

    approval_id: str
    actor: str = "system"
    granted: bool = True


class HTTPRecordingFixture(BaseModel):
    """Store one inline request/response replay fixture."""

    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)


class FilesystemEntryFixture(BaseModel):
    """Represent one deterministic filesystem fixture entry."""

    path: str
    content: str = ""
    writable: bool = False


class QueueMessageFixture(BaseModel):
    """Represent one deterministic queue message."""

    queue: str
    body: dict[str, Any] = Field(default_factory=dict)
    message_id: str | None = None


class WebhookEventFixture(BaseModel):
    """Represent one deterministic webhook event."""

    endpoint: str
    method: str = "POST"
    payload: dict[str, Any] = Field(default_factory=dict)
    event_id: str | None = None


class FixturesConfig(BaseModel):
    """Reusable fixtures that influence determinism and policy enforcement."""

    approvals: list[ApprovalFixture] = Field(default_factory=list)
    http_recordings: list[HTTPRecordingFixture] = Field(default_factory=list)
    filesystem: list[FilesystemEntryFixture] = Field(default_factory=list)
    queue_messages: list[QueueMessageFixture] = Field(default_factory=list)
    webhook_events: list[WebhookEventFixture] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatabaseSeed(BaseModel):
    """SQL statements to run before a scenario starts."""

    statements: list[str] = Field(default_factory=list)


class APISeed(BaseModel):
    """HTTP request/response pairs for record-replay."""

    recordings: list[dict[str, Any]] = Field(default_factory=list)


class BrowserSessionSeed(BaseModel):
    """Placeholder schema for future browser/session replay."""

    sessions: list[dict[str, Any]] = Field(default_factory=list)


class EnvironmentConfig(BaseModel):
    """Environment configuration for the scenario."""

    kind: EnvironmentKind = EnvironmentKind.SIMULATED
    database: DatabaseSeed | None = None
    api: APISeed | None = None
    browser_session: BrowserSessionSeed | None = None


class SessionConfig(BaseModel):
    """Capture session expectations for stateful agents."""

    enabled: bool = False
    session_id: str | None = None
    stateful: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffConfig(BaseModel):
    """Declare expected multi-agent handoff behavior."""

    enabled: bool = False
    expected_edges: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanFeedbackConfig(BaseModel):
    """Declare expected human feedback checkpoints."""

    enabled: bool = False
    required_actors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamingConfig(BaseModel):
    """Declare streaming-output expectations."""

    enabled: bool = False
    expected_chunk_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RealtimeConfig(BaseModel):
    """Declare realtime transport expectations."""

    enabled: bool = False
    transport: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    """Declare MCP servers and resources involved in the scenario."""

    enabled: bool = False
    servers: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterAgentConfig(BaseModel):
    """Declare non-local inter-agent protocol expectations."""

    enabled: bool = False
    protocol: str | None = None
    topology: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssertionConfig(BaseModel):
    """One evaluator invocation attached to a scenario."""

    evaluator: str
    params: dict[str, Any] = Field(default_factory=dict)
    pillar: str | None = None


class PolicyConfig(BaseModel):
    """One policy rule compiled into an assertion at evaluation time."""

    evaluator: str
    params: dict[str, Any] = Field(default_factory=dict)
    policy_id: str | None = None
    pillar: str | None = "safety"


class BaselineConfig(BaseModel):
    """Baseline comparison settings for regression detection."""

    mode: BaselineMode = BaselineMode.COMBINED
    trace_file: str
    compare_tool_calls: bool = False
    compare_metrics: bool = False
    metrics: list[str] = Field(default_factory=lambda: list(DEFAULT_BASELINE_METRICS))
    metrics_tolerance: float = Field(default=0.1, ge=0)


class ScenarioConfig(BaseModel):
    """Complete definition of a single ASE scenario."""

    spec_version: int = SCENARIO_SPEC_VERSION
    scenario_id: str
    name: str
    description: str = ""
    agent: AgentConfig
    agent_runtime: AgentRuntimeConfig | None = None
    adapter: AdapterConfig | None = None
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    fixtures: FixturesConfig = Field(default_factory=FixturesConfig)
    session: SessionConfig | None = None
    handoffs: HandoffConfig | None = None
    human_feedback: HumanFeedbackConfig | None = None
    streaming: StreamingConfig | None = None
    realtime: RealtimeConfig | None = None
    mcp: MCPConfig | None = None
    inter_agent: InterAgentConfig | None = None
    assertions: list[AssertionConfig] = Field(default_factory=list)
    policies: list[PolicyConfig] = Field(default_factory=list)
    baselines: BaselineConfig | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    run_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def runtime_mode(self) -> AgentRuntimeMode:
        """Return the effective execution mode for the scenario."""
        if self.agent_runtime is None or self.agent_runtime.mode is None:
            return AgentRuntimeMode.PROXY
        return self.agent_runtime.mode

    @property
    def certification_level(self) -> CertificationLevel | None:
        """Infer a coarse certification level from scenario capabilities."""
        if self.mcp and self.mcp.enabled:
            return CertificationLevel.MCP
        if self.handoffs and self.handoffs.enabled:
            return CertificationLevel.MULTI_AGENT
        if self.session and self.session.enabled:
            return CertificationLevel.STATEFUL
        if self.streaming and self.streaming.enabled:
            return CertificationLevel.REALTIME
        if self.agent_runtime is not None:
            return CertificationLevel.CORE
        return None
