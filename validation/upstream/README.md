# Upstream Validation Harnesses

This directory contains ASE-owned harnesses for validating real upstream
framework repos without vendoring those repos into ASE.

Bootstrap the upstream workspaces into `.upstream/`:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
python scripts/bootstrap_upstream_validations.py --framework langgraph-python
python scripts/bootstrap_upstream_validations.py --framework pydantic-ai-python
python scripts/bootstrap_upstream_validations.py --framework openai-agents-js
```

Then run ASE against the harnesses here:

```bash
ase test validation/upstream/openai-agents-python/ase-scenario.yaml
ase certify validation/upstream/openai-agents-python/ase-manifest.yaml
```

