"""HTTP proxy used by proxy-mode scenarios and `ase watch`.

The proxy exists so ASE can observe outbound HTTP requests and HTTPS tunnel
hops without changing the agent's own model, prompts, or reasoning loop.
"""

from __future__ import annotations

import asyncio
import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlunsplit

import httpx

from ase.core.recorder import Recorder
from ase.core.resolver import Resolver
from ase.trace.model import ToolCallKind

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


@dataclass(slots=True)
class ParsedRequest:
    """Capture one proxied HTTP request in a transport-neutral shape."""

    method: str
    target_url: str
    version: str
    headers: list[tuple[str, str]]
    body: bytes


class HTTPProxy:
    """Forward HTTP traffic and record either direct requests or CONNECT tunnels."""

    def __init__(
        self,
        *,
        resolver: Resolver,
        recorder: Recorder,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self._resolver = resolver
        self._recorder = recorder
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._active_connections: set[asyncio.Task[None]] = set()
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=30.0,
            trust_env=False,
        )

    @property
    def address(self) -> str:
        """Return the proxy URL that agent subprocesses should use."""
        sockets = getattr(self._server, "sockets", []) if self._server is not None else []
        if sockets:
            port = int(sockets[0].getsockname()[1])
            return f"http://{self._host}:{port}"
        return f"http://{self._host}:{self._port or 0}"

    async def start(self) -> None:
        """Bind a loopback HTTP proxy that accepts proxied client requests."""
        port = self._port or _reserve_port()
        self._server = await asyncio.start_server(self._handle_client, self._host, port)

    async def stop(self) -> None:
        """Close the listening socket and shared outbound client."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._active_connections:
            await asyncio.gather(*list(self._active_connections), return_exceptions=True)
        await self._client.aclose()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Parse one proxied request, forward it, and relay the response."""
        task = asyncio.current_task()
        if task is not None:
            self._active_connections.add(task)
        try:
            request = await _read_request(reader)
            if request.method.upper() == "CONNECT":
                await self._tunnel_request(request, reader, writer)
                return
            response = await self._forward_request(request)
            await _write_response(writer, request.version, response)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await _write_simple_response(writer, 502, str(exc).encode("utf-8", errors="replace"))
        finally:
            if task is not None:
                self._active_connections.discard(task)
            writer.close()
            await writer.wait_closed()

    async def _forward_request(self, request: ParsedRequest) -> httpx.Response:
        """Resolve one proxied request against fixtures or the real network."""
        response = await self._fixture_or_network_response(request)
        self._recorder.record_tool_call(
            kind=ToolCallKind.HTTP_API,
            method=request.method.upper(),
            target=request.target_url,
            payload=_request_payload(request),
            response_status=response.status_code,
            response_body=_response_body(response),
        )
        return response

    async def _tunnel_request(
        self,
        request: ParsedRequest,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Tunnel HTTPS CONNECT traffic while still recording the proxy hop."""
        host, port = _split_connect_target(request.target_url)
        upstream_reader, upstream_writer = await asyncio.open_connection(host, port)
        self._recorder.record_tool_call(
            kind=ToolCallKind.HTTP_API,
            method="CONNECT",
            target=f"https://{host}:{port}",
            payload={"headers": dict(request.headers), "tunneled": True},
            response_status=200,
            response_body={"status": "connection established"},
        )
        response_line = f"{request.version} 200 Connection Established\r\n\r\n"
        client_writer.write(response_line.encode("iso-8859-1"))
        await client_writer.drain()
        try:
            await asyncio.gather(
                _pipe_stream(client_reader, upstream_writer),
                _pipe_stream(upstream_reader, client_writer),
            )
        finally:
            upstream_writer.close()
            await upstream_writer.wait_closed()

    async def _fixture_or_network_response(self, request: ParsedRequest) -> httpx.Response:
        """Prefer replay fixtures when configured, otherwise forward upstream."""
        provider = self._resolver.resolve(ToolCallKind.HTTP_API)
        if provider is not None:
            payload = await provider.request(
                request.method,
                request.target_url,
                payload=_request_payload(request),
            )
            body = json.dumps(payload).encode("utf-8")
            return httpx.Response(
                200,
                headers={"content-type": "application/json", "content-length": str(len(body))},
                content=body,
                request=httpx.Request(request.method, request.target_url),
            )
        return await self._client.request(
            request.method,
            request.target_url,
            headers=dict(_forward_headers(request.headers)),
            content=request.body,
        )


async def _read_request(reader: asyncio.StreamReader) -> ParsedRequest:
    """Read one HTTP/1.x request from an asyncio stream."""
    header_blob = await reader.readuntil(b"\r\n\r\n")
    header_text = header_blob.decode("iso-8859-1")
    lines = header_text.split("\r\n")
    request_line = lines[0]
    method, raw_target, version = request_line.split(" ", 2)
    headers = _parse_headers(lines[1:])
    body = await _read_body(reader, headers)
    target_url = _normalize_target(method, raw_target, headers)
    return ParsedRequest(
        method=method,
        target_url=target_url,
        version=version,
        headers=headers,
        body=body,
    )


def _parse_headers(lines: list[str]) -> list[tuple[str, str]]:
    """Keep incoming header order stable while dropping the terminal blank line."""
    headers: list[tuple[str, str]] = []
    for line in lines:
        if not line:
            continue
        name, value = line.split(":", 1)
        headers.append((name.strip(), value.strip()))
    return headers


async def _read_body(
    reader: asyncio.StreamReader,
    headers: list[tuple[str, str]],
) -> bytes:
    """Read request content when the client declared a fixed content length."""
    for name, value in headers:
        if name.lower() != "content-length":
            continue
        length = max(0, int(value))
        if length == 0:
            return b""
        return await reader.readexactly(length)
    return b""


def _normalize_target(
    method: str,
    raw_target: str,
    headers: list[tuple[str, str]],
) -> str:
    """Convert proxy request targets into absolute URLs for forwarding."""
    if method.upper() == "CONNECT":
        return raw_target
    if "://" in raw_target:
        return raw_target
    host = next((value for name, value in headers if name.lower() == "host"), "")
    if not host:
        raise ValueError("missing host header for proxied request")
    return urlunsplit(("http", host, raw_target, "", ""))


def _forward_headers(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop hop-by-hop proxy headers before forwarding upstream."""
    forwarded: list[tuple[str, str]] = []
    for name, value in headers:
        if name.lower() in _HOP_BY_HOP_HEADERS:
            continue
        forwarded.append((name, value))
    return forwarded


def _request_payload(request: ParsedRequest) -> dict[str, Any]:
    """Capture outbound request details in a stable tool-call payload."""
    payload: dict[str, Any] = {"headers": dict(request.headers)}
    if request.body:
        decoded = request.body.decode("utf-8", errors="replace")
        try:
            payload["body"] = json.loads(decoded)
        except json.JSONDecodeError:
            payload["body"] = decoded
    return payload


def _response_body(response: httpx.Response) -> dict[str, Any] | None:
    """Capture JSON responses structurally and fall back to plain text otherwise."""
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        try:
            value = response.json()
        except ValueError:
            return {"text": response.text}
        if isinstance(value, dict):
            return value
        return {"value": value}
    return {"text": response.text}


async def _write_response(
    writer: asyncio.StreamWriter,
    version: str,
    response: httpx.Response,
) -> None:
    """Relay one forwarded upstream response back to the proxied client."""
    status_line = f"{version} {response.status_code} {response.reason_phrase}\r\n"
    writer.write(status_line.encode("iso-8859-1"))
    headers = _response_headers(response)
    for name, value in headers:
        writer.write(f"{name}: {value}\r\n".encode("iso-8859-1"))
    writer.write(b"\r\n")
    writer.write(response.content)
    await writer.drain()


def _response_headers(response: httpx.Response) -> list[tuple[str, str]]:
    """Preserve upstream headers while removing hop-by-hop proxy fields."""
    headers = [
        (name, value)
        for name, value in response.headers.items()
        if name.lower() not in _HOP_BY_HOP_HEADERS
    ]
    content_length = str(len(response.content))
    if not any(name.lower() == "content-length" for name, _ in headers):
        headers.append(("content-length", content_length))
    return headers


def _split_connect_target(target: str) -> tuple[str, int]:
    """Parse one CONNECT target into the host and port the tunnel should reach."""
    if ":" not in target:
        return target, 443
    host, port_text = target.rsplit(":", 1)
    return host, int(port_text)


async def _pipe_stream(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Forward bytes between the client and the upstream tunnel endpoint."""
    while not reader.at_eof():
        chunk = await reader.read(65536)
        if not chunk:
            return
        writer.write(chunk)
        await writer.drain()


async def _write_simple_response(
    writer: asyncio.StreamWriter,
    status_code: int,
    body: bytes,
) -> None:
    """Return a short plaintext error response for malformed proxy requests."""
    status_line = f"HTTP/1.1 {status_code} {_reason_phrase(status_code)}\r\n"
    writer.write(status_line.encode("iso-8859-1"))
    writer.write(
        f"content-length: {len(body)}\r\ncontent-type: text/plain\r\n\r\n".encode(
            "iso-8859-1"
        )
    )
    writer.write(body)
    await writer.drain()


def _reason_phrase(status_code: int) -> str:
    """Provide stable short status text for proxy-generated responses."""
    if status_code == 501:
        return "Not Implemented"
    if status_code == 502:
        return "Bad Gateway"
    return "Error"


def _reserve_port() -> int:
    """Allocate a free TCP port before the proxy starts listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
