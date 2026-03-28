# Example Workflows

## Proxy quickstart

```bash
ase test examples/customer-support/scenarios/refund-happy-path.yaml
ase watch -- python3 path/to/your_agent.py
```

Proxy-mode note:
- direct HTTP requests are recorded as HTTP tool calls
- HTTPS traffic through `CONNECT` is recorded as a tunnel hop unless your agent
  also emits richer adapter or instrumented events

## Instrumented quickstart

```bash
ase test examples/instrumented-python/scenario.yaml
```

## Python adapter quickstart

```bash
pip install -r examples/openai-agents-python/requirements.txt
pip install -r examples/langgraph-python/requirements.txt
pip install -r examples/pydantic-ai-python/requirements.txt
pip install -r examples/mcp-python/requirements.txt

ase test examples/openai-agents-python/scenario.yaml
ase certify examples/openai-agents-python/manifest.yaml

ase test examples/langgraph-python/scenario.yaml
ase certify examples/langgraph-python/manifest.yaml

ase test examples/pydantic-ai-python/scenario.yaml
ase certify examples/pydantic-ai-python/manifest.yaml

ase test examples/mcp-python/scenario.yaml
ase certify examples/mcp-python/manifest.yaml
```

## TypeScript adapter quickstart

```bash
npm install --prefix examples/openai-agents-typescript
ase test examples/openai-agents-typescript/scenario.yaml
ase certify examples/openai-agents-typescript/manifest.yaml
```

The TypeScript example uses the official `@openai/agents` package from npm
with a deterministic fake model so ASE can certify the workflow locally.

## Real upstream framework validation

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
ase test validation/upstream/openai-agents-python/ase-scenario.yaml
ase certify validation/upstream/openai-agents-python/ase-manifest.yaml

python scripts/bootstrap_upstream_validations.py --framework langgraph-python
ase test validation/upstream/langgraph-python/ase-scenario.yaml
ase certify validation/upstream/langgraph-python/ase-manifest.yaml

python scripts/bootstrap_upstream_validations.py --framework pydantic-ai-python
ase test validation/upstream/pydantic-ai-python/ase-scenario.yaml
ase certify validation/upstream/pydantic-ai-python/ase-manifest.yaml

python scripts/bootstrap_upstream_validations.py --framework openai-agents-js
ase test validation/upstream/openai-agents-js/ase-scenario.yaml
ase certify validation/upstream/openai-agents-js/ase-manifest.yaml
```
