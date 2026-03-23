# Releasing ASE

## Recommended package identity

- PyPI distribution: `ase-python`
- Import path: `ase`
- CLI command: `ase`

`ase` itself is already taken on PyPI by a different project, so publishing ASE
under `ase-python` avoids a naming collision while keeping the user-facing CLI
simple.

## Recommended release strategy

Use Trusted Publishing from GitHub Actions.

Why:
- no long-lived PyPI API token in repo secrets
- repeatable release path from signed tags
- artifact build and `twine check` happen before publish

## One-time setup

1. Create a PyPI project named `ase-python`.
2. In PyPI, configure Trusted Publishing for this GitHub repository.
3. In GitHub, use the `pypi` environment for the publish job.
4. Make sure the repository URL and docs URL are final before the first public release.

## Local verification

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install build twine
python -m build
python -m twine check dist/*
python -m pip install dist/ase_python-0.1.0-py3-none-any.whl
ase --help
```

## GitHub release flow

```bash
git tag v0.1.0
git push origin v0.1.0
```

The `publish-pypi` workflow will:
- build the wheel and sdist
- run `twine check`
- publish to PyPI through Trusted Publishing

## Suggested release order

1. Publish to TestPyPI first.
2. Verify `pip install -i https://test.pypi.org/simple/ ase-python`.
3. Confirm `ase --help` and one example scenario work.
4. Publish the same tag to PyPI.

## Notes

- Keep the package name `ase-python` even if the CLI stays `ase`.
- Do not publish as `ase`; that name is already in use.
- Keep the root GitHub `README.md` richer than `README_PYPI.md`, because PyPI
  does not handle the full repo-doc link structure as cleanly.
