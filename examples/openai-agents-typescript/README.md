# OpenAI Agents TypeScript Example

This example runs a deterministic offline flow using the official
[`@openai/agents`](https://www.npmjs.com/package/@openai/agents) package and
emits ASE adapter events.

Install and run:

```bash
npm ci --prefix examples/openai-agents-typescript
node examples/openai-agents-typescript/agent.ts
PYTHONPATH=src ./.venv/bin/python -m ase.cli.main adapter verify examples/openai-agents-typescript/events.generated.jsonl
PYTHONPATH=src ./.venv/bin/python -m ase.cli.main certify examples/openai-agents-typescript/manifest.yaml
```
