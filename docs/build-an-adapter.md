# How to Build an Adapter

1. Emit ASE adapter events using the official SDK surface in `src/ase/adapters` or `sdk/typescript`.
2. Choose a stable adapter name and framework/language identity.
3. Map runtime lifecycle, tool calls, sessions, handoffs, approvals, and streaming onto the event protocol.
4. Inject deterministic fixtures without changing ASE core semantics.
5. Add a conformance manifest under `conformance/launch/<adapter-name>/` and, if
   the adapter targets a reusable certification family, mirror it under
   `conformance/bundles/<family>/<adapter-name>/`.
6. Run `ase adapter verify`, `ase test`, and `ase certify` on the emitted event
   stream.
7. Ensure the adapter can surface runtime provenance:
   - framework name/version
   - adapter name/version
   - execution mode
   - conformance bundle version when certified

Neutral-core rule:

- if a change only exists for one framework, keep it in the adapter or harness
- only move behavior into ASE core when it clearly generalizes across at least two frameworks or execution modes

Release-candidate rule:

- official adapters should be proven against the real upstream runtime or
  official package, not a framework-shaped stub
- example quickstarts and CI jobs should run the same commands users see in the
  docs

Use the launch adapters as references:

- `openai-agents-python`
- `langgraph-python`
- `pydantic-ai-python`
- `openai-agents-typescript`
- `mcp-python`
