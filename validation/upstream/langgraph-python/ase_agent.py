"""Run a real upstream LangGraph flow and emit ASE adapter events."""

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
SPAN_ID = "executor-agent:issue_refund"
TARGET_URL = "https://api.example.com/refunds"


class GraphState(TypedDict, total=False):
    """Carry the user request and final execution result through the graph."""

    request: str
    result: str


def _parse_args() -> argparse.Namespace:
    """Accept an optional event output path for certification runs."""
    default_path = Path(
        os.environ.get(
            "ASE_ADAPTER_EVENT_SOURCE",
            str(Path(__file__).with_name("events.generated.jsonl")),
        )
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events-out",
        type=Path,
        default=default_path,
    )
    return parser.parse_args()


def _build_graph(adapter: LangGraphAdapter) -> CompiledStateGraph:
    """Create a deterministic two-node LangGraph handoff flow."""
    from langgraph.graph import END, START, StateGraph

    def planner(state: GraphState) -> GraphState:
        adapter.handoff(
            PLANNER_ID,
            EXECUTOR_ID,
            name="delegate_refund",
            data={"request": state["request"]},
        )
        return state

    def executor(state: GraphState) -> GraphState:
        adapter.tool_start(
            EXECUTOR_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            name="issue_refund",
            data={"request": state["request"]},
        )
        adapter.tool_end(
            EXECUTOR_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            data={"status_code": 200},
        )
        return {"result": "refunded ord-001"}

    graph = StateGraph(GraphState)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    return graph.compile()


def main() -> int:
    """Execute a real upstream LangGraph run for ASE validation."""
    from ase.adapters.frameworks import LangGraphAdapter
    from ase.adapters.io import JsonlFileEventSink

    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = LangGraphAdapter(JsonlFileEventSink(args.events_out))
    graph = _build_graph(adapter)
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
