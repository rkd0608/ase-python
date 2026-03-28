"""Direct runtime execution helpers for adapter and instrumented scenarios."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import NamedTuple

from ase.adapters.protocol import read_and_verify
from ase.adapters.replay import trace_from_adapter_events
from ase.errors import RuntimeModeError
from ase.scenario.model import AgentRuntimeMode, ScenarioConfig
from ase.trace.model import Trace, TraceStatus


class CompletedRun(NamedTuple):
    """Carry subprocess completion details into trace reconstruction."""

    returncode: int
    stderr: bytes


async def run_direct_runtime(scenario: ScenarioConfig, debug: bool = False) -> Trace:
    """Execute non-proxy scenarios and return a native trace from emitted events."""
    if scenario.runtime_mode not in {AgentRuntimeMode.ADAPTER, AgentRuntimeMode.INSTRUMENTED}:
        raise RuntimeModeError(f"unsupported direct runtime mode: {scenario.runtime_mode.value}")
    event_path = _event_path(scenario)
    completed = await _run_agent_process(scenario, event_path, debug=debug)
    if not event_path.exists():
        raise RuntimeModeError(f"adapter event file not found: {event_path}")
    events, verification = read_and_verify(event_path)
    if not verification.passed:
        details = ", ".join(verification.errors)
        raise RuntimeModeError(f"adapter event stream failed verification: {details}")
    trace = trace_from_adapter_events(events, scenario.scenario_id, scenario.name)
    _override_runtime_mode(trace, scenario)
    stderr_text = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
    trace.stderr_output = stderr_text or None
    if completed.returncode != 0:
        trace.status = TraceStatus.FAILED
        trace.error_message = (
            trace.stderr_output or f"agent exited with code {completed.returncode}"
        )
    return trace


async def _run_agent_process(
    scenario: ScenarioConfig,
    event_path: Path,
    *,
    debug: bool,
) -> CompletedRun:
    """Run one direct-runtime subprocess with the event sink exported explicitly."""
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(scenario.agent.env)
    env["ASE_ADAPTER_EVENT_SOURCE"] = str(event_path)
    process = await asyncio.create_subprocess_exec(
        *scenario.agent.command,
        env=env,
        stdout=None if debug else asyncio.subprocess.PIPE,
        stderr=None if debug else asyncio.subprocess.PIPE,
    )
    try:
        if debug:
            await asyncio.wait_for(process.wait(), timeout=scenario.agent.timeout_seconds)
            return CompletedRun(returncode=process.returncode or 0, stderr=b"")
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=scenario.agent.timeout_seconds,
        )
        return CompletedRun(returncode=process.returncode or 0, stderr=stderr or b"")
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeModeError(
            f"agent timed out after {scenario.agent.timeout_seconds}s"
        ) from exc


def _event_path(scenario: ScenarioConfig) -> Path:
    """Resolve event output relative to the scenario source file when possible."""
    runtime = scenario.agent_runtime
    if runtime is None or not runtime.event_source:
        raise RuntimeModeError("agent_runtime.event_source is required for direct runtime modes")
    source = Path(runtime.event_source)
    if source.is_absolute():
        return source
    scenario_source = Path(str(scenario.run_metadata.get("source", ""))).resolve()
    if scenario_source.is_file():
        return scenario_source.parent / source
    return Path.cwd() / source


def _override_runtime_mode(trace: Trace, scenario: ScenarioConfig) -> None:
    """Keep replay-derived traces aligned with the scenario's requested mode."""
    provenance = trace.runtime_provenance
    if provenance is None:
        return
    provenance.mode = scenario.runtime_mode.value
