"""SimulationEngine — the main orchestration loop for a scenario run.

Ties together: environments, proxy, recorder, and evaluation.
The engine is the only component that knows how all the pieces connect.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING, Any

import structlog

from ase.core.recorder import Recorder
from ase.core.resolver import Resolver
from ase.core.runtime_modes import run_direct_runtime
from ase.errors import ASEError
from ase.scenario.model import (
    AgentRuntimeMode,
    APISeed,
    EnvironmentKind,
    ScenarioConfig,
)
from ase.trace.model import Trace, TraceStatus

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

_POLL_INTERVAL_S = 0.1

# Hosts that must bypass the ASE proxy — LLM providers and auth endpoints.
# ASE intercepts tool calls (database, APIs, email), never model inference calls.
_PROXY_BYPASS_HOSTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",  # Gemini
    "api.mistral.ai",
    "api.cohere.com",
    "bedrock-runtime.amazonaws.com",
    "oauth2.googleapis.com",
    "auth.openai.com",
]


def _build_no_proxy(existing: str) -> str:
    """Merge existing NO_PROXY with ASE's LLM bypass list, deduplicating."""
    current = {h.strip() for h in existing.split(",") if h.strip()}
    merged = sorted(current | set(_PROXY_BYPASS_HOSTS))
    return ",".join(merged)


class RunResult:
    """The outcome of a single scenario execution."""

    def __init__(self, trace: Trace, environments: dict[str, Any]) -> None:
        self.trace = trace
        # Expose environments so evaluators can inspect post-run state
        self.database: Any | None = environments.get("database")
        self.api: Any | None = environments.get("api")
        self.email: Any | None = environments.get("email")
        self.filesystem: Any | None = environments.get("filesystem")
        self.queue: Any | None = environments.get("queue")


class SimulationEngine:
    """Orchestrates a full scenario run.

    For each scenario:
    1. Build and set up environments from scenario config
    2. Start the HTTP proxy (if using HTTP interception)
    3. Launch the agent subprocess
    4. Wait for the agent to finish (or timeout)
    5. Tear down environments
    6. Return a RunResult containing the Trace
    """

    def __init__(self, proxy_host: str = "127.0.0.1", proxy_port: int = 0) -> None:
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port  # 0 = auto-allocate per run

    async def run(
        self, scenario: ScenarioConfig, debug: bool = False
    ) -> RunResult:
        """Execute a scenario and return the RunResult.

        Never raises — errors are recorded in the trace with status=ERROR.
        Each call creates its own proxy with a fresh port, so concurrent
        calls to run() on the same engine instance are safe.
        """
        recorder = Recorder(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            tags={tag: "true" for tag in scenario.tags},
        )
        self._seed_trace(recorder, scenario)
        if scenario.runtime_mode != AgentRuntimeMode.PROXY:
            try:
                trace = await run_direct_runtime(scenario, debug=debug)
            except ASEError as exc:
                log.error("engine_run_failed", scenario=scenario.scenario_id, error=str(exc))
                trace = recorder.finish(status=TraceStatus.ERROR, error_message=str(exc))
            except Exception as exc:
                log.error("engine_run_unexpected", scenario=scenario.scenario_id, error=str(exc))
                trace = recorder.finish(
                    status=TraceStatus.ERROR,
                    error_message=f"unexpected error: {exc}",
                )
            return RunResult(trace=trace, environments={})

        resolver = Resolver()
        environments: dict[str, Any] = {}

        # Proxy is created per-run so each concurrent scenario gets its own port
        from ase.core.proxy import HTTPProxy

        proxy = HTTPProxy(
            resolver=resolver,
            recorder=recorder,
            host=self._proxy_host,
            port=self._proxy_port,
        )
        try:
            environments = await self._setup_environments(scenario, resolver)
            await proxy.start()
            trace = await self._execute_agent(
                scenario, recorder, resolver, proxy.address, debug=debug
            )
        except ASEError as exc:
            log.error("engine_run_failed", scenario=scenario.scenario_id, error=str(exc))
            trace = recorder.finish(status=TraceStatus.ERROR, error_message=str(exc))
        except Exception as exc:
            log.error("engine_run_unexpected", scenario=scenario.scenario_id, error=str(exc))
            trace = recorder.finish(
                status=TraceStatus.ERROR,
                error_message=f"unexpected error: {exc}",
            )
        finally:
            await proxy.stop()
            await self._teardown_environments(environments)

        return RunResult(trace=trace, environments=environments)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_trace(self, recorder: Recorder, scenario: ScenarioConfig) -> None:
        """Persist approvals and replay metadata before the agent launches."""
        runtime = scenario.agent_runtime
        recorder.set_runtime_provenance(
            mode=scenario.runtime_mode.value,
            framework=runtime.framework if runtime else None,
            framework_version=runtime.version if runtime else None,
            adapter_name=runtime.adapter_name if runtime else None,
            event_source=runtime.event_source if runtime else None,
            metadata=dict(runtime.metadata) if runtime else None,
        )
        for approval in scenario.fixtures.approvals:
            recorder.record_approval(
                approval_id=approval.approval_id,
                actor=approval.actor,
                granted=approval.granted,
            )
        recorder.set_determinism_metadata(
            fixture_payload=json.loads(scenario.fixtures.model_dump_json()),
            replay_key=f"{scenario.scenario_id}:spec-v{scenario.spec_version}",
        )

    async def _setup_environments(
        self, scenario: ScenarioConfig, resolver: Resolver
    ) -> dict[str, Any]:
        """Instantiate, seed, and register all scenario environments."""
        from ase.environments.api import APIEnvironment
        from ase.environments.database import DatabaseEnvironment
        from ase.environments.email import EmailEnvironment
        from ase.environments.filesystem import FilesystemEnvironment
        from ase.environments.queue import QueueEnvironment
        from ase.trace.model import ToolCallKind

        environments: dict[str, Any] = {}
        env_config = scenario.environment

        if env_config.kind == EnvironmentKind.REAL:
            # No simulation — pass through to real backends
            return environments

        if env_config.database is not None:
            db = DatabaseEnvironment(seed=env_config.database)
            await db.setup()
            resolver.register(ToolCallKind.DATABASE, db)
            environments["database"] = db

        api_seed = _merged_api_seed(scenario)
        if api_seed.recordings:
            api = APIEnvironment(seed=api_seed)
            await api.setup()
            resolver.register(ToolCallKind.HTTP_API, api)
            environments["api"] = api

        # Email is always available in simulated mode
        if env_config.kind == EnvironmentKind.SIMULATED:
            email = EmailEnvironment()
            await email.setup()
            resolver.register(ToolCallKind.EMAIL, email)
            environments["email"] = email
            if scenario.fixtures.filesystem:
                filesystem = FilesystemEnvironment(scenario.fixtures.filesystem)
                await filesystem.setup()
                environments["filesystem"] = filesystem
            if scenario.fixtures.queue_messages or scenario.fixtures.webhook_events:
                queue = QueueEnvironment(
                    queue_messages=scenario.fixtures.queue_messages,
                    webhook_events=scenario.fixtures.webhook_events,
                )
                await queue.setup()
                environments["queue"] = queue

        return environments

    async def _execute_agent(
        self,
        scenario: ScenarioConfig,
        recorder: Recorder,
        resolver: Resolver,
        proxy_address: str,
        debug: bool = False,
    ) -> Trace:
        """Launch the agent subprocess and wait for it to complete.

        proxy_address: the actual address of the proxy started for this run.
        debug: when True, inherit terminal stdio so agent output streams live.
        """
        agent_cfg = scenario.agent
        proxy_env = {
            **os.environ,  # inherit PATH, API keys, etc. from the parent process
            "HTTP_PROXY": proxy_address,
            "HTTPS_PROXY": proxy_address,
            "ASE_TRACE_ID": recorder.trace_id,
            # LLM provider hosts must bypass the proxy — ASE intercepts tool calls,
            # not the agent's model calls. Append to any existing NO_PROXY value.
            "NO_PROXY": _build_no_proxy(os.environ.get("NO_PROXY", "")),
            **agent_cfg.env,  # scenario-level overrides win
        }

        log.info(
            "agent_launching",
            scenario=scenario.scenario_id,
            command=agent_cfg.command,
        )

        if debug:
            return await self._execute_agent_debug(scenario, agent_cfg, proxy_env, recorder)

        try:
            process = await asyncio.create_subprocess_exec(
                *agent_cfg.command,
                env=proxy_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=agent_cfg.timeout_seconds,
            )
        except TimeoutError:
            log.warning("agent_timeout", scenario=scenario.scenario_id)
            return recorder.finish(
                status=TraceStatus.ERROR,
                error_message=f"agent timed out after {agent_cfg.timeout_seconds}s",
            )
        except Exception as exc:
            return recorder.finish(
                status=TraceStatus.ERROR,
                error_message=f"failed to launch agent: {exc}",
            )

        exit_code = process.returncode or 0
        log.info("agent_exited", scenario=scenario.scenario_id, exit_code=exit_code)

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        status = TraceStatus.PASSED if exit_code == 0 else TraceStatus.FAILED
        # Always capture stderr; only treat it as error_message on failure
        return recorder.finish(
            status=status,
            error_message=stderr_text if exit_code != 0 else None,
            stderr_output=stderr_text or None,
        )

    async def _execute_agent_debug(
        self,
        scenario: ScenarioConfig,
        agent_cfg: object,
        proxy_env: dict[str, str],
        recorder: Recorder,
    ) -> Trace:
        """Debug variant — inherits terminal stdio so output streams live."""
        from ase.scenario.model import AgentConfig
        assert isinstance(agent_cfg, AgentConfig)
        try:
            process = await asyncio.create_subprocess_exec(
                *agent_cfg.command,
                env=proxy_env,
                # no PIPE — output goes directly to the terminal
            )
            await asyncio.wait_for(process.wait(), timeout=agent_cfg.timeout_seconds)
        except TimeoutError:
            log.warning("agent_timeout", scenario=scenario.scenario_id)
            return recorder.finish(
                status=TraceStatus.ERROR,
                error_message=f"agent timed out after {agent_cfg.timeout_seconds}s",
            )
        except Exception as exc:
            return recorder.finish(
                status=TraceStatus.ERROR,
                error_message=f"failed to launch agent: {exc}",
            )
        exit_code = process.returncode or 0
        log.info("agent_exited", scenario=scenario.scenario_id, exit_code=exit_code)
        status = TraceStatus.PASSED if exit_code == 0 else TraceStatus.FAILED
        return recorder.finish(status=status)

    @staticmethod
    async def _teardown_environments(environments: dict[str, Any]) -> None:
        """Tear down all environments, logging but not re-raising errors."""
        from ase.environments.base import EnvironmentProvider

        for name, env in environments.items():
            if isinstance(env, EnvironmentProvider):
                try:
                    await env.teardown()
                except Exception as exc:
                    log.warning("teardown_error", environment=name, error=str(exc))


def _merged_api_seed(scenario: ScenarioConfig) -> APISeed:
    """Merge API recordings declared in environment and fixtures."""
    environment_recordings = list(
        scenario.environment.api.recordings if scenario.environment.api else []
    )
    fixture_recordings = [
        fixture.model_dump() for fixture in scenario.fixtures.http_recordings
    ]
    return APISeed(recordings=environment_recordings + fixture_recordings)
