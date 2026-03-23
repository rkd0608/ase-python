# ASE

ASE is the open pre-production testing and certification layer for agent systems.

ASE helps teams validate what an agent **did**, not just what it **said**:

- `ase watch` shows live tool calls
- `ase test` runs scenarios with assertions on behavior
- `ase compare` diffs two runs after a prompt, model, or adapter change

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install ase-python
```

## Quickstart

```bash
ase test examples/customer-support/scenarios/refund-happy-path.yaml
ase compare /tmp/baseline.trace.json /tmp/candidate.trace.json
```

## What ASE Does

- captures tool calls, state transitions, handoffs, and protocol events
- evaluates traces with assertions like `tool_called`, `max_tool_calls`, and policy checks
- certifies adapter-backed frameworks through a neutral event protocol
- works across proxy, instrumented, and adapter-backed agent runtimes

## Project Links

- Source repository: see the project homepage that publishes this package
- Documentation: see `README.md` and `docs/` in the source repository

## Status

ASE is release-hardening toward a broader framework certification story. The
current public positioning is:

> the open pre-production testing and certification layer for agent systems
