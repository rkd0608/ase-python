# Silent Prompt Regression

Framework: OpenAI Agents Python  
Narrative: a harmless-seeming prompt or model tweak causes the same refund tool
to fire twice.

Without ASE:
- the agent still says "refunded ord-001"
- the duplicate side effect or added cost slips through review

With ASE:
- `ase test` fails on `max_tool_calls`
- `ase compare` shows the duplicate tool-call regression immediately

Commands:

```bash
PYTHONPATH=src ase test validation/case_studies/openai_prompt_regression/scenario.bad.yaml
PYTHONPATH=src ase test validation/case_studies/openai_prompt_regression/scenario.fixed.yaml
PYTHONPATH=src ase replay validation/case_studies/openai_prompt_regression/events.bad.jsonl --scenario-id case-openai-prompt-regression-bad --scenario-name "OpenAI Prompt Regression Bad" --trace-out /tmp/case-openai-bad.trace.json
PYTHONPATH=src ase replay validation/case_studies/openai_prompt_regression/events.fixed.jsonl --scenario-id case-openai-prompt-regression-fixed --scenario-name "OpenAI Prompt Regression Fixed" --trace-out /tmp/case-openai-fixed.trace.json
PYTHONPATH=src ase compare /tmp/case-openai-bad.trace.json /tmp/case-openai-fixed.trace.json --output markdown
```

Observed ASE output:

```text
FAIL case-openai-prompt-regression-bad trace=01KMC0XC1SJ6Z5BY67EJA1196H
ase_score=0.80
scenario failed: case-openai-prompt-regression-bad

PASS case-openai-prompt-regression-fixed trace=01KMC0XD9EBATK2QSQC514PZ0S
ase_score=1.00
```

Observed diff:

```markdown
# ASE Trace Diff

- Baseline: `01KMC0XMZJKXH1Q9WX0D25MJ29`
- Candidate: `01KMC0XN7H7FB1TXWF18W8T8N8`
- Status: `passed` -> `passed`
- Evaluation: `None` -> `None`
- ASE score delta: `0.00`
- Tool calls: `2` -> `1`
```

Event evidence:

```text
---BAD---
tool_start span=openai-regression-agent:issue_refund:1
tool_end   span=openai-regression-agent:issue_refund:1
tool_start span=openai-regression-agent:issue_refund:2
tool_end   span=openai-regression-agent:issue_refund:2

---FIXED---
tool_start span=openai-regression-agent:issue_refund:1
tool_end   span=openai-regression-agent:issue_refund:1
```
