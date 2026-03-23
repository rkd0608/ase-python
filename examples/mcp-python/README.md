# MCP Python Example

This example uses the real [`mcp`](https://modelcontextprotocol.io/docs/learn)
Python package and a `FastMCP` server to certify an MCP-backed resource read
and approval-gated resource write through ASE's adapter runtime path.

Run:

```bash
pip install -r examples/mcp-python/requirements.txt
PYTHONPATH=src ./.venv/bin/python -m ase.cli.main test examples/mcp-python/scenario.yaml
PYTHONPATH=src ./.venv/bin/python -m ase.cli.main certify examples/mcp-python/manifest.yaml
```
