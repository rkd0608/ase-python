import { appendFile, mkdir, rm } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { z } from 'zod';

import {
  Agent,
  run,
  setDefaultModelProvider,
  tool,
  Usage,
} from '../../../.upstream/openai-agents-js/packages/agents-core/src/index.ts';
import type { ModelResponse } from '../../../.upstream/openai-agents-js/packages/agents-core/src/model.ts';
import type {
  AssistantMessageItem,
  FunctionCallItem,
} from '../../../.upstream/openai-agents-js/packages/agents-core/src/types/protocol.ts';
import {
  FakeModel,
  FakeModelProvider,
} from '../../../.upstream/openai-agents-js/packages/agents-core/test/stubs.ts';

const AGENT_ID = 'openai-agents-js-refund-agent';
const SPAN_ID = 'openai-agents-js-refund-agent:issue_refund';
const TARGET_URL = 'https://api.example.com/refunds';
const DEFAULT_EVENT_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  'events.generated.jsonl',
);
const EVENT_PATH = resolve(
  process.env.ASE_ADAPTER_EVENT_SOURCE ?? DEFAULT_EVENT_PATH,
);

type AdapterEvent = {
  protocol_version: number;
  event_type: string;
  event_id: string;
  timestamp_ms: number;
  span_id?: string;
  agent_id?: string;
  name?: string;
  tool_kind?: string;
  method?: string;
  target?: string;
  status?: string;
  message?: string;
  data?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

let nextEventId = 0;

function metadata(): Record<string, unknown> {
  return {
    adapter_name: 'openai-agents-js',
    framework: 'openai-agents-js',
    language: 'typescript',
    transport: 'jsonl-stdio',
  };
}

function functionToolCall(): FunctionCallItem {
  return {
    id: 'fc_1',
    type: 'function_call',
    name: 'issue_refund',
    callId: 'call_1',
    status: 'completed',
    arguments: '{"order_id":"ord-001"}',
    providerData: {},
  };
}

function finalMessage(): AssistantMessageItem {
  return {
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
  };
}

async function emit(event: AdapterEvent): Promise<void> {
  await appendFile(EVENT_PATH, `${JSON.stringify(event)}\n`, 'utf-8');
}

async function emitEvent(
  eventType: string,
  extra: Omit<
    AdapterEvent,
    'protocol_version' | 'event_type' | 'event_id' | 'timestamp_ms'
  >,
): Promise<void> {
  nextEventId += 1;
  await emit({
    protocol_version: 1,
    event_type: eventType,
    event_id: `evt_${nextEventId}`,
    timestamp_ms: Date.now(),
    metadata: metadata(),
    ...extra,
  });
}

function buildAgent(): Agent {
  const modelResponses: ModelResponse[] = [
    { output: [functionToolCall()], usage: new Usage() },
    { output: [finalMessage()], usage: new Usage() },
  ];
  const model = new FakeModel(modelResponses);
  const issueRefundTool = tool({
    name: 'issue_refund',
    description: 'Issue one deterministic refund',
    parameters: z.object({ order_id: z.string() }),
    execute: async ({ order_id }: { order_id: string }) => {
      await emitEvent('tool_start', {
        agent_id: AGENT_ID,
        span_id: SPAN_ID,
        tool_kind: 'http_api',
        method: 'POST',
        target: TARGET_URL,
        name: 'issue_refund',
        data: { order_id },
      });
      await emitEvent('tool_end', {
        agent_id: AGENT_ID,
        span_id: SPAN_ID,
        tool_kind: 'http_api',
        method: 'POST',
        target: TARGET_URL,
        status: 'passed',
        data: { order_id, status_code: 200 },
      });
      return `refunded ${order_id}`;
    },
  });
  return new Agent({
    name: AGENT_ID,
    instructions: 'Issue a refund with one tool call.',
    model,
    tools: [issueRefundTool],
  });
}

async function main(): Promise<number> {
  await mkdir(dirname(EVENT_PATH), { recursive: true });
  await rm(EVENT_PATH, { force: true });
  setDefaultModelProvider(new FakeModelProvider());
  const agent = buildAgent();
  let status = 'passed';
  await emitEvent('agent_start', { agent_id: AGENT_ID, name: AGENT_ID });
  try {
    const result = await run(agent, 'refund ord-001');
    console.log(result.finalOutput);
    console.log(EVENT_PATH);
    return 0;
  } catch (error) {
    status = 'failed';
    throw error;
  } finally {
    await emitEvent('agent_end', {
      agent_id: AGENT_ID,
      status,
      message: status === 'passed' ? undefined : 'agent run failed',
    });
  }
}

main().then(
  (code) => process.exit(code),
  (error: unknown) => {
    console.error(error);
    process.exit(1);
  },
);

