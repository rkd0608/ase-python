# OpenAI Agents TypeScript Example

This example runs a deterministic offline flow using the official
[`@openai/agents`](https://www.npmjs.com/package/@openai/agents) package and
emits ASE adapter events.

Install and run:

```bash
npm install --prefix examples/openai-agents-typescript
node examples/openai-agents-typescript/agent.ts
PYTHONPATH=src python3 -m ase.cli.main adapter verify examples/openai-agents-typescript/events.generated.jsonl
PYTHONPATH=src python3 -m ase.cli.main certify examples/openai-agents-typescript/manifest.yaml

This example uses the official `@openai/agents` package with a deterministic
fake model so the ASE workflow stays local and reproducible.
```
