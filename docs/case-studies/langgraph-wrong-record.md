# Wrong Record Mutation

Framework: LangGraph  
Narrative: the planner/executor flow still completes, but the executor mutates
the wrong order id.

Without ASE:
- the multi-agent flow appears healthy
- the wrong customer record is mutated underneath

With ASE:
- `ase test` fails because the expected refund target is never observed
- the event stream shows `ord-999` in the bad run and `ord-001` after the fix

Commands:

```bash
PYTHONPATH=src ase test validation/case_studies/langgraph_wrong_record/scenario.bad.yaml
PYTHONPATH=src ase test validation/case_studies/langgraph_wrong_record/scenario.fixed.yaml
```

Observed ASE output:

```text
FAIL case-langgraph-wrong-record-bad trace=01KMC10HVMPJ6N96V2M064KJ60
ase_score=0.80
scenario failed: case-langgraph-wrong-record-bad

PASS case-langgraph-wrong-record-fixed trace=01KMC10JH9MFQQWZKMVZVV2WW7
ase_score=1.00
```

Assertion-specific signal:

```text
assertion_evaluated evaluator=tool_called passed=False score=0.0
assertion_evaluated evaluator=tool_called passed=True score=1.0
```

Event evidence:

```json
// bad
{"event_type":"tool_start","target":"https://api.example.com/refunds/ord-999"}

// fixed
{"event_type":"tool_start","target":"https://api.example.com/refunds/ord-001"}
```
