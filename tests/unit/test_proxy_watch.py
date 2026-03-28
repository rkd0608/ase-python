from __future__ import annotations

import asyncio
import sys
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ase.cli.main import app
from ase.core.proxy import HTTPProxy
from ase.core.recorder import Recorder
from ase.core.resolver import Resolver
from ase.trace.model import TraceStatus

runner = CliRunner()


class _Handler(BaseHTTPRequestHandler):
    requests: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        self.requests.append(self.path)
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        del format, args


def _start_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _write_proxy_agent(path: Path, target_url: str) -> None:
    script = textwrap.dedent(
        f"""
        import os
        import urllib.request

        proxy = urllib.request.ProxyHandler({{"http": os.environ["HTTP_PROXY"]}})
        opener = urllib.request.build_opener(proxy)
        with opener.open("{target_url}") as response:
            print(response.read().decode("utf-8"))
        """
    ).strip()
    path.write_text(script + "\n", encoding="utf-8")


def _write_sleep_agent(path: Path, seconds: int) -> None:
    path.write_text(f"import time\ntime.sleep({seconds})\n", encoding="utf-8")


def test_watch_records_http_tool_call(tmp_path: Path) -> None:
    server, thread = _start_server()
    try:
        agent = tmp_path / "proxy_agent.py"
        host, port = server.server_address
        _write_proxy_agent(agent, f"http://{host}:{port}/orders/ord-001")
        result = runner.invoke(
            app,
            ["watch", "--timeout", "10", "--", sys.executable, str(agent)],
        )
        assert result.exit_code == 0, result.output
        assert "tool_calls: 1" in result.output
        assert _Handler.requests == ["/orders/ord-001"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        _Handler.requests.clear()


def test_watch_enforces_timeout(tmp_path: Path) -> None:
    agent = tmp_path / "sleep_agent.py"
    _write_sleep_agent(agent, seconds=3)
    started = time.monotonic()
    result = runner.invoke(
        app,
        ["watch", "--timeout", "1", "--", sys.executable, str(agent)],
    )
    elapsed = time.monotonic() - started
    assert result.exit_code == 1, result.output
    assert "agent timed out after 1s" in result.output
    assert elapsed < 3


def test_proxy_mode_test_captures_http_tool_call(tmp_path: Path) -> None:
    server, thread = _start_server()
    try:
        agent = tmp_path / "proxy_agent.py"
        host, port = server.server_address
        _write_proxy_agent(agent, f"http://{host}:{port}/orders/ord-001")
        scenario = tmp_path / "proxy_scenario.yaml"
        scenario.write_text(
            textwrap.dedent(
                f"""
                scenario_id: proxy-http
                name: Proxy HTTP
                agent:
                  command:
                    - {sys.executable}
                    - {agent}
                  timeout_seconds: 10
                environment:
                  kind: real
                assertions:
                  - evaluator: tool_called
                    params:
                      kind: http_api
                      minimum: 1
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["test", str(scenario)])
        assert result.exit_code == 0, result.output
        assert "PASS proxy-http" in result.output
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        _Handler.requests.clear()


@pytest.mark.asyncio
async def test_proxy_supports_connect_tunneling() -> None:
    async def handle_echo(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        payload = await reader.read(65536)
        writer.write(payload)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    upstream = await asyncio.start_server(handle_echo, "127.0.0.1", 0)
    upstream_host, upstream_port = upstream.sockets[0].getsockname()[:2]
    recorder = Recorder(scenario_id="proxy-connect", scenario_name="proxy-connect")
    proxy = HTTPProxy(resolver=Resolver(), recorder=recorder)
    await proxy.start()
    proxy_host, proxy_port = proxy.address.removeprefix("http://").split(":")
    client_reader, client_writer = await asyncio.open_connection(proxy_host, int(proxy_port))
    connect_request = (
        f"CONNECT {upstream_host}:{upstream_port} HTTP/1.1\r\n"
        f"Host: {upstream_host}:{upstream_port}\r\n\r\n"
    ).encode("ascii")
    try:
        client_writer.write(connect_request)
        await client_writer.drain()
        response_head = await asyncio.wait_for(client_reader.readuntil(b"\r\n\r\n"), timeout=3)
        assert b"200 Connection Established" in response_head
        client_writer.write(b"ping")
        await client_writer.drain()
        assert await asyncio.wait_for(client_reader.readexactly(4), timeout=3) == b"ping"
    finally:
        client_writer.close()
        await client_writer.wait_closed()
        upstream.close()
        await upstream.wait_closed()
        await proxy.stop()
    trace = recorder.finish(status=TraceStatus.PASSED)
    assert trace.metrics.total_tool_calls == 1
    assert trace.events[0].tool_call is not None
    assert trace.events[0].tool_call.method == "CONNECT"
