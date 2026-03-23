# Certify a Framework

To certify a framework with ASE:

1. create an ASE-owned harness that runs a real upstream framework flow
2. emit adapter events through the neutral ASE protocol
3. define a scenario and conformance manifest
4. run `ase test` for operator-facing validation
5. run `ase certify` for formal certification output

Example:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
ase test validation/upstream/openai-agents-python/ase-scenario.yaml
ase certify validation/upstream/openai-agents-python/ase-manifest.yaml
```

Rules:

- keep framework-specific runtime logic out of `src/ase` core
- keep harnesses under `validation/upstream/`
- fetch upstream repos on demand into `.upstream/`
- generate compatibility outputs from certification artifacts only

