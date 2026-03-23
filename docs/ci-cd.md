# ASE in CI/CD

Recommended CI flow:

1. install ASE with `PIP_CONSTRAINT=constraints/py311.txt`
2. fetch/bootstrap any upstream framework repos you plan to certify
3. run `ase test` for operator-facing validation
4. run `ase certify` for each launch or bundle manifest
5. publish certification JSON artifacts
6. generate the compatibility matrix from those artifacts only
7. fail the pipeline on any certification regression

Example artifact types:

- certification JSON
- native ASE trace JSON
- OTEL JSON export
- generated compatibility matrix Markdown

Matrix generation must consume certification artifacts only, for example:

```bash
python scripts/generate_compatibility_matrix.py \
  docs/compatibility-matrix.generated.md \
  certification-artifacts
```

Supported CI patterns:

- Python-only jobs for proxy, instrumented, OpenAI Agents Python, LangGraph Python,
  and PydanticAI upstream validation
- mixed Python + Node jobs for the OpenAI Agents JS upstream validation path

Reference bootstrap step:

```bash
python scripts/bootstrap_upstream_validations.py --framework openai-agents-python
ase test validation/upstream/openai-agents-python/ase-scenario.yaml
ase certify validation/upstream/openai-agents-python/ase-manifest.yaml
```

Reference pipelines live in:

- `.github/workflows/certify.yml`
- `.gitlab-ci.yml`
