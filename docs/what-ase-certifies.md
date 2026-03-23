# What ASE Certifies

ASE certifies observable agent behavior, not marketing claims.

Today, ASE focuses on:

- whether the agent made the expected tool calls
- whether runtime side effects stayed within expected bounds
- whether a framework adapter emits a valid ASE event stream
- whether a run can be replayed into a valid ASE trace
- whether scenario assertions pass against that trace

ASE does **not** certify:

- the quality of a model's internal reasoning
- business correctness without explicit assertions
- production safety unless policy checks are configured
- all frameworks in the ecosystem by default

Certification levels are capability-oriented:

- `core`
- `stateful`
- `multi_agent`
- `mcp`
- `realtime`

