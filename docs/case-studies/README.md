# ASE Case Studies

These case studies are grounded in real runs against fetched upstream
frameworks, not static mock screenshots.

Bootstrap the required upstream workspaces first:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
python scripts/bootstrap_upstream_validations.py --framework langgraph-python
python scripts/bootstrap_upstream_validations.py --framework pydantic-ai-python
```

Then run the scenarios from the repo root with `PYTHONPATH=src`.

Available studies:
- [Silent Prompt Regression](./openai-prompt-regression.md)
- [Missing Approval Before Refund](./pydantic-approval-gate.md)
- [Wrong Record Mutation](./langgraph-wrong-record.md)
