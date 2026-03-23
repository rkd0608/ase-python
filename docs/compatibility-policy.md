# Compatibility Policy

ASE treats these as stable public contracts:

- scenario schema
- adapter event protocol
- append-only trace schema
- certification manifest/result schemas

Rules:

1. existing trace and schema fields are append-only
2. framework-specific behavior belongs in adapters or harnesses, not core
3. compatibility matrix entries come only from real certification artifacts
4. public docs and quickstarts must use CI-exercised commands

This repo does not claim universal-standard status yet. It currently presents
ASE as the open pre-production testing and certification layer for agent
systems.

