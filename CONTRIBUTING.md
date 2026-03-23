# Contributing

ASE's core must remain framework-neutral.

Before adding code:

1. Ask whether the change generalizes across at least two frameworks or execution modes.
2. If not, put it in an adapter, example harness, or conformance bundle instead of `src/ase` core.
3. Keep the adapter event protocol and append-only trace schema as the compatibility boundary.

Contribution rules:

- no framework-specific runtime imports in ASE core
- no framework-specific fields in the core trace schema unless they generalize
- keep upstream runtime harnesses in `validation/upstream/`, not core
- no docs examples that have not been exercised in CI
- no compatibility-matrix edits by hand; generate it from certification artifacts only
- fetch third-party upstream repos into `.upstream/` instead of vendoring them
