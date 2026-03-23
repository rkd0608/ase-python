# Compatibility Matrix

Generate this page from certification artifacts:

```bash
python scripts/generate_compatibility_matrix.py \
  docs/compatibility-matrix.generated.md \
  /path/to/certification-artifacts
```

The generated matrix should list:

- framework
- language
- adapter
- adapter version
- bundle family
- certification level
- conformance bundle version
- pass/fail status
- generated artifact timestamp
- source artifact path or URL

Do not edit the generated matrix by hand. It is a build artifact derived from
real `ase certify` outputs and is intended to fail CI when certification
coverage regresses.
