# Setup and Reproducibility

ASE supports a reproducible Python 3.11 core path and a mixed Python + Node
path for the TypeScript validation harness.

## Python-only setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
export PIP_CONSTRAINT=constraints/py311.txt
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Why the constraint file exists:

- it pins a Python 3.11-compatible `mitmproxy` line
- it prevents dependency drift between local runs and CI
- it keeps lint/test/type-check behavior closer to the documented path

## Upstream framework isolation

When a real upstream framework needs newer or conflicting dependencies, keep it
in its own venv and point ASE at it through `agent.command`.

Chosen default:

- ASE core lives in its own supported `.venv`
- upstream framework validation may run in dedicated `.upstream` workspaces
- certification artifacts are the output contract, not a shared-process import

This is the supported way to validate frameworks like OpenAI Agents Python,
LangGraph, and PydanticAI without forcing ASE core to adopt their dependency
constraints.

Bootstrap one upstream workspace:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
ase test validation/upstream/openai-agents-python/ase-scenario.yaml
```

The bootstrap script prefers `python3.12` for upstream Python framework
workspaces when it is available. ASE core itself still uses the documented
Python 3.11 path.

## Mixed Python + Node setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
export PIP_CONSTRAINT=constraints/py311.txt
python -m pip install --upgrade pip
pip install -e ".[dev]"
python scripts/bootstrap_upstream_validations.py --framework openai-agents-js
npm install --prefix examples/openai-agents-typescript
```

## Clean verification commands

Proxy and instrumented examples:

```bash
ase test examples/customer-support/scenarios/refund-happy-path.yaml
ase test examples/instrumented-python/scenario.yaml
```

Adapter examples:

```bash
ase test examples/openai-agents-python/scenario.yaml
ase test examples/langgraph-python/scenario.yaml
ase test examples/pydantic-ai-python/scenario.yaml
ase test examples/openai-agents-typescript/scenario.yaml
ase test examples/mcp-python/scenario.yaml
```

Upstream validation examples:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
python scripts/bootstrap_upstream_validations.py --framework langgraph-python
python scripts/bootstrap_upstream_validations.py --framework pydantic-ai-python
python scripts/bootstrap_upstream_validations.py --framework openai-agents-js

ase test validation/upstream/openai-agents-python/ase-scenario.yaml
ase test validation/upstream/langgraph-python/ase-scenario.yaml
ase test validation/upstream/pydantic-ai-python/ase-scenario.yaml
ase test validation/upstream/openai-agents-js/ase-scenario.yaml
```

Full public example matrix:

```bash
ase examples run
```

## Troubleshooting

If your local `.venv` looks corrupted, rebuild it instead of trying to patch a
broken install in place:

```bash
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
export PIP_CONSTRAINT=constraints/py311.txt
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

If ASE fails at startup with:

```text
ModuleNotFoundError: No module named 'pydantic.plugin._loader'
```

your venv has a broken `pydantic` install. Rebuild the venv or force-reinstall
`pydantic` inside it. This is an environment problem, not an ASE command
compatibility issue.

If an upstream framework needs conflicting versions, keep it in `.upstream/`
and keep ASE itself in the constrained core environment.

## Supported CI environments

- Python-only CI for proxy, instrumented, and Python adapter examples
- Mixed Python + Node CI for the full example matrix and TypeScript adapter path

The reference jobs live in:

- `.github/workflows/certify.yml`
- `.gitlab-ci.yml`
