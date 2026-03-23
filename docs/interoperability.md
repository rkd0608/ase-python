# OTEL and MCP Interoperability

ASE currently provides:

- OTEL-like export from native ASE traces
- OTEL-like import back into ASE traces
- MCP-oriented adapter and example coverage inside the repo

Near-term open-source positioning:

- OTEL import/export is part of the public interoperability story
- MCP remains supported work in progress and is not part of the main OSS hero claim

Use OTEL export/import like this:

```bash
ase replay validation/upstream/openai-agents-python/events.generated.jsonl \
  --scenario-id upstream-openai-agents-python \
  --scenario-name "Upstream OpenAI Agents Python" \
  --trace-out /tmp/upstream.trace.json

ase report /tmp/upstream.trace.json --output otel-json --out-file /tmp/upstream.otel.json
ase import otel /tmp/upstream.otel.json --trace-out /tmp/upstream.imported.trace.json
```

