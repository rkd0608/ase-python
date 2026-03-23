# Neutral Core Boundaries

ASE stays framework-neutral by keeping the core limited to:

- scenario execution modes
- adapter event protocol
- trace schema
- evaluation engine
- reporting, certification, and conformance

Framework-specific behavior belongs in:

- `src/ase/adapters/frameworks/*` for adapter SDK helpers
- `examples/*` for supported example workflows
- `validation/upstream/*` for real upstream validation harnesses
- conformance bundles and manifests

Rules for new work:

1. Do not add framework-specific semantics to ASE core unless they generalize across at least two frameworks.
2. Do not make `ase test`, `ase certify`, or the trace schema depend on one framework's private runtime concepts.
3. Put framework runtime hooks in adapters, not evaluators or reporters.
4. Treat the adapter protocol and append-only trace schema as the stability boundary.

Use this rule in reviews:

- if a change only exists to make one framework green, it belongs in an adapter or harness unless the abstraction clearly generalizes.
