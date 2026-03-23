"""Load conformance manifests and execute certification checks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import yaml

from ase.adapters.protocol import read_and_verify
from ase.adapters.replay import trace_from_adapter_events
from ase.conformance.model import (
    ConformanceCheckResult,
    ConformanceManifest,
    ConformanceResult,
    resolve_case_path,
)
from ase.conformance.schema import validate_manifest_dict, validate_result_dict
from ase.errors import ConformanceError
from ase.evaluation.engine import EvaluationEngine
from ase.evaluation.trace_summary import attach_summary
from ase.scenario.parser import parse_file


def load_manifest(path: Path) -> ConformanceManifest:
    """Load a YAML or JSON conformance manifest from disk."""
    if not path.exists():
        raise ConformanceError(f"conformance manifest not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConformanceError(f"failed to read conformance manifest {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConformanceError(f"invalid conformance manifest YAML in {path}: {exc}") from exc
    validate_manifest_dict(data, str(path))
    try:
        return ConformanceManifest.model_validate(data)
    except Exception as exc:
        raise ConformanceError(f"failed to validate conformance manifest {path}: {exc}") from exc


def certify_manifest(
    manifest: ConformanceManifest,
    manifest_path: Path,
) -> ConformanceResult:
    """Run all conformance cases and build a certification result."""
    checks: list[ConformanceCheckResult] = []
    eval_engine = EvaluationEngine()

    for case in manifest.cases:
        event_path = resolve_case_path(manifest_path, case.adapter_events)
        events, verification = read_and_verify(event_path)
        checks.append(
            ConformanceCheckResult(
                check_id="adapter_contract",
                case_id=case.case_id,
                passed=verification.passed,
                message="adapter event stream validates"
                if verification.passed
                else "adapter event stream violates the contract",
                details=verification.model_dump(),
            )
        )
        trace = trace_from_adapter_events(events, case.case_id, case.name)

        observed_event_types = set(verification.event_type_counts)
        for event_type in case.required_event_types:
            passed = event_type in observed_event_types
            checks.append(
                ConformanceCheckResult(
                    check_id=f"requires_event_type:{event_type}",
                    case_id=case.case_id,
                    passed=passed,
                    message=f"required event type {event_type}",
                    details={"observed": sorted(observed_event_types)},
                )
            )

        observed_protocols = {event.protocol for event in events if event.protocol}
        for protocol in case.required_protocols:
            passed = protocol in observed_protocols
            checks.append(
                ConformanceCheckResult(
                    check_id=f"requires_protocol:{protocol}",
                    case_id=case.case_id,
                    passed=passed,
                    message=f"required protocol {protocol}",
                    details={"observed": sorted(observed_protocols)},
                )
            )

        for key, minimum in case.minimum_fidelity.items():
            observed = _observed_fidelity(trace, key)
            checks.append(
                ConformanceCheckResult(
                    check_id=f"minimum_fidelity:{key}",
                    case_id=case.case_id,
                    passed=observed >= minimum,
                    message=f"minimum fidelity for {key}",
                    details={"minimum": minimum, "observed": observed},
                )
            )

        if case.scenario:
            scenario_path = resolve_case_path(manifest_path, case.scenario)
            scenario = parse_file(scenario_path)
            summary = eval_engine.evaluate(
                trace=trace,
                assertions=scenario.assertions,
                context={},
            )
            attach_summary(trace, summary)
            checks.append(
                ConformanceCheckResult(
                    check_id="scenario_assertions",
                    case_id=case.case_id,
                    passed=summary.passed,
                    message="scenario assertions passed"
                    if summary.passed
                    else "scenario assertions failed",
                    details={
                        "ase_score": summary.ase_score,
                        "failed_count": summary.failed_count,
                    },
                )
            )

    return ConformanceResult(
        manifest_id=manifest.manifest_id,
        manifest_name=manifest.name,
        adapter_name=manifest.adapter_name,
        adapter_version=manifest.adapter_version,
        bundle_family=manifest.bundle_family,
        bundle_version=manifest.bundle_version,
        framework=manifest.framework,
        language=manifest.language,
        certification_level=manifest.certification_target,
        methodology_profiles=list(manifest.methodology_profiles),
        passed=all(check.passed for check in checks),
        checks=checks,
    )


def sign_result(
    result: ConformanceResult,
    signing_key_env: str | None,
) -> ConformanceResult:
    """Attach a digest and optional HMAC signature to a certification result."""
    payload = json.dumps(
        result.model_dump(exclude={"report_digest_sha256", "signature_algorithm", "signature"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    updated = result.model_copy(update={"report_digest_sha256": digest})
    if not signing_key_env:
        validate_result_dict(updated.model_dump(), "certification result")
        return updated

    signing_key = os.environ.get(signing_key_env)
    if not signing_key:
        raise ConformanceError(f"missing signing key env var: {signing_key_env}")

    signature = hmac.new(
        signing_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    signed = updated.model_copy(
        update={"signature_algorithm": "hmac-sha256", "signature": signature}
    )
    validate_result_dict(signed.model_dump(), "signed certification result")
    return signed


def _observed_fidelity(trace: object, key: str) -> int:
    """Map bundle fidelity keys onto concrete counts from a replayed trace."""
    from ase.trace.model import Trace

    assert isinstance(trace, Trace)
    counts = {
        "tool_calls": trace.metrics.total_tool_calls,
        "session_events": len(trace.session_events),
        "handoff_edges": len(trace.handoff_edges),
        "protocol_events": len(trace.protocol_events),
        "agent_graph_nodes": len(trace.agent_graph.nodes),
        "external_trace_refs": len(trace.external_trace_refs),
    }
    return counts.get(key, 0)
