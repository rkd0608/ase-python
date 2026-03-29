import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { Agent, Usage, run, tool } from '@openai/agents';
import { z } from 'zod';

const AGENT_ID = 'openai-agents-typescript-example';
const SPAN_ID = 'openai-agents-typescript-example:issue_refund';
const TARGET = 'https://api.example.com/refunds';

function parseEventsOut() {
  const argIndex = process.argv.indexOf('--events-out');
  if (argIndex !== -1 && process.argv[argIndex + 1]) {
    return resolve(process.argv[argIndex + 1]);
  }
  return resolve(
    process.env.ASE_ADAPTER_EVENT_SOURCE ?? 'examples/openai-agents-typescript/events.generated.jsonl',
  );
}

function event(eventType, extra = {}) {
  return {
    protocol_version: 1,
    event_type: eventType,
    event_id: `${eventType}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp_ms: Date.now(),
    metadata: {
      adapter_name: 'openai-agents-typescript',
      framework: 'openai-agents-js',
      language: 'typescript',
      transport: 'jsonl-stdio',
    },
    ...extra,
  };
}

function modelResponses() {
  return [
    {
      output: [
        {
          id: 'fc_1',
          type: 'function_call',
          name: 'issue_refund',
          callId: 'call_1',
          status: 'completed',
          arguments: '{"order_id":"ord-001"}',
          providerData: {},
        },
      ],
      usage: new Usage(),
    },
    {
      output: [
        {
          type: 'message',
          role: 'assistant',
          status: 'completed',
          content: [
            {
              type: 'output_text',
              text: 'refunded ord-001',
              providerData: { annotations: [] },
            },
          ],
          providerData: {},
        },
      ],
      usage: new Usage(),
    },
  ];
}

class FakeModel {
  constructor(responses) {
    this.responses = [...responses];
  }

  async getResponse() {
    const response = this.responses.shift();
    if (!response) {
      throw new Error('no fake model response available');
    }
    return response;
  }

  async *getStreamedResponse() {
    throw new Error('streaming is not implemented in this example');
  }
}

function buildAgent(events) {
  const issueRefund = tool({
    name: 'issue_refund',
    description: 'Issue one deterministic refund',
    parameters: z.object({ order_id: z.string() }),
    execute: async ({ order_id }) => {
      events.push(
        event('tool_start', {
          agent_id: AGENT_ID,
          span_id: SPAN_ID,
          tool_kind: 'http_api',
          method: 'POST',
          target: TARGET,
          name: 'issue_refund',
          data: { order_id },
        }),
      );
      events.push(
        event('tool_end', {
          agent_id: AGENT_ID,
          span_id: SPAN_ID,
          tool_kind: 'http_api',
          method: 'POST',
          target: TARGET,
          status: 'passed',
          data: { status_code: 200, order_id },
        }),
      );
      return `refunded ${order_id}`;
    },
  });

  return new Agent({
    name: AGENT_ID,
    instructions: 'Issue a refund with one tool call.',
    model: new FakeModel(modelResponses()),
    tools: [issueRefund],
  });
}

async function main() {
  const eventPath = parseEventsOut();
  const events = [event('agent_start', { agent_id: AGENT_ID, name: AGENT_ID })];
  const agent = buildAgent(events);
  const result = await run(agent, 'refund ord-001');
  events.push(event('agent_end', { agent_id: AGENT_ID, status: 'passed' }));
  await mkdir(dirname(eventPath), { recursive: true });
  await writeFile(eventPath, `${events.map((item) => JSON.stringify(item)).join('\n')}\n`, 'utf-8');
  console.log(result.finalOutput);
  process.exit(0);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
