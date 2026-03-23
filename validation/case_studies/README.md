## ASE Case Studies

These case studies use real upstream frameworks through ASE-owned harnesses.

Each directory contains:
- `ase_agent.py`: harness that runs a real upstream framework flow
- `scenario.bad.yaml`: intentionally regressed scenario
- `scenario.fixed.yaml`: corrected scenario

Run them from the repo root after bootstrapping upstream dependencies:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
python scripts/bootstrap_upstream_validations.py --framework langgraph-python
python scripts/bootstrap_upstream_validations.py --framework pydantic-ai-python
```

Then run:

```bash
PYTHONPATH=src ase test validation/case_studies/openai_prompt_regression/scenario.bad.yaml
PYTHONPATH=src ase test validation/case_studies/openai_prompt_regression/scenario.fixed.yaml
```
