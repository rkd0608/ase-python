"""Run a real LangGraph flow with a controllable wrong-record mutation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM_ROOT = ROOT / ".upstream" / "langgraph"
PACKAGE_ROOT = UPSTREAM_ROOT / "libs" / "langgraph"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from ase.adapters.frameworks import LangGraphAdapter

PLANNER_ID = "planner-agent"
EXECUTOR_ID = "executor-agent"


class GraphState(TypedDict, total=False):
    """Carry the request and result through the handoff flow."""

    request: str
    result: str


def _parse_args() -> argparse.Namespace:
    """Expose a bad and fixed variant without changing ASE core."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["bad", "fixed"], default="fixed")
    parser.add_argument(
        "--events-out",
        type=Path,
        default=Path(
            os.environ.get(
                "ASE_ADAPTER_EVENT_SOURCE",
                str(Path(__file__).with_name("events.generated.jsonl")),
            )
        ),
    )
    return parser.parse_args()


def _target_url(variant: str) -> str:
    """Encode the wrong-record regression directly in the tool target."""
    order_id = "ord-999" if variant == "bad" else "ord-001"
    return f"https://api.example.com/refunds/{order_id}"


def _build_graph(adapter: LangGraphAdapter, variant: str) -> CompiledStateGraph:
    """Use a real LangGraph handoff while varying only the mutated record."""
    from langgraph.graph import END, START, StateGraph

    def planner(state: GraphState) -> GraphState:
        adapter.handoff(PLANNER_ID, EXECUTOR_ID, name="delegate_refund", data=state)
        return state

    def executor(state: GraphState) -> GraphState:
        target = _target_url(variant)
        adapter.tool_start(
            EXECUTOR_ID,
            span_id=f"{EXECUTOR_ID}:issue_refund",
            tool_kind="http_api",
            method="POST",
            target=target,
            name="issue_refund",
            data={"request": state["request"]},
        )
        adapter.tool_end(
            EXECUTOR_ID,
            span_id=f"{EXECUTOR_ID}:issue_refund",
            tool_kind="http_api",
            method="POST",
            target=target,
            data={"status_code": 200},
        )
        return {"result": target}

    graph = StateGraph(GraphState)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    return graph.compile()


def main() -> int:
    """Execute the wrong-record case study through a real LangGraph runtime."""
    from ase.adapters.frameworks import LangGraphAdapter
    from ase.adapters.io import JsonlFileEventSink

    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = LangGraphAdapter(JsonlFileEventSink(args.events_out))
    graph = _build_graph(adapter, args.variant)
    status = "passed"
    adapter.agent_start(PLANNER_ID, name=PLANNER_ID)
    adapter.agent_start(EXECUTOR_ID, name=EXECUTOR_ID, parent_agent_id=PLANNER_ID)
    try:
        result = graph.invoke({"request": "refund ord-001"})
        print(result["result"])
        print(args.events_out)
        return 0
    except BaseException:
        status = "failed"
        raise
    finally:
        adapter.agent_end(EXECUTOR_ID, status=status)
        adapter.agent_end(PLANNER_ID, status=status)


if __name__ == "__main__":
    raise SystemExit(main())
