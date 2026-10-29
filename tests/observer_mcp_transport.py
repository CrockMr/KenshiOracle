"""Owned MCP stdio transport with verified per-process CPU endpoints."""
from __future__ import annotations

import asyncio
import copy
import json
import math
import os
from pathlib import Path
import secrets
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import psutil

from live_mcp_battle import Adapter
from observer_mcp_server import HANDSHAKE_PROTOCOL, process_identity


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = (ROOT / "tests/observer_mcp_server.py").resolve()
IDENTITY_KEYS = {"pid", "created_at", "executable", "cmdline", "parent_pid"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def normalized_path(value):
    return os.path.normcase(str(Path(value).resolve()))


def check_record(record, *, server=False):
    require(isinstance(record, dict) and set(record) == IDENTITY_KEYS | ({"token"} if server else set()),
            "Invalid process identity fields")
    require(type(record["pid"]) is int and record["pid"] > 0 and type(record["parent_pid"]) is int
            and record["parent_pid"] > 0 and record["pid"] != record["parent_pid"], "Invalid identity PID")
    require(type(record["created_at"]) in (float, int) and math.isfinite(record["created_at"])
            and record["created_at"] > 0, "Invalid identity creation time")
    require(isinstance(record["executable"], str) and Path(record["executable"]).is_absolute(),
            "Invalid identity executable")
    require(isinstance(record["cmdline"], list) and record["cmdline"]
            and all(isinstance(x, str) for x in record["cmdline"]), "Invalid identity command")


class ServerIdentityVerifier:
    """Read only named PIDs, allowing at most one Windows venv launcher."""

    def __init__(self, payload, *, token, command, controller_identity, allowed_executables,
                 process_factory=None):
        self.process_factory = process_factory or psutil.Process
        require(isinstance(payload, dict) and payload.get("protocol") == HANDSHAKE_PROTOCOL,
                "Invalid server handshake protocol")
        self.expected = copy.deepcopy(payload.get("identity"))
        check_record(self.expected, server=True)
        require(self.expected["token"] == token, "Server handshake token differs")
        self.command = list(command)
        self.controller = copy.deepcopy(controller_identity)
        check_record(self.controller)
        self.allowed = list(allowed_executables)
        self.allowed_normalized = {normalized_path(p) for p in self.allowed}
        require(self.expected["pid"] != self.controller["pid"], "Server identity names controller")
        self.parent_chain = None
        _, chain = self.verify()
        self.parent_chain = copy.deepcopy(chain)

    def _read(self, pid):
        try:
            process = self.process_factory(pid)
            record = process_identity(process)
            check_record(record)
            require(process.is_running(), "Process exited during identity verification")
            return process, record
        except (psutil.Error, OSError) as exc:
            raise RuntimeError("Process identity unavailable for PID " + str(pid)) from exc

    def _check_command(self, record):
        require(normalized_path(record["executable"]) in self.allowed_normalized,
                "Server/launcher executable differs")
        require(record["cmdline"][1:] == self.command[1:]
                and normalized_path(record["cmdline"][0]) in self.allowed_normalized,
                "Server/launcher command differs")

    def verify(self):
        process, actual = self._read(self.expected["pid"])
        require(actual == {k: self.expected[k] for k in IDENTITY_KEYS}, "Server identity changed")
        self._check_command(actual)
        _, parent = self._read(actual["parent_pid"])
        chain = [parent]
        if parent["pid"] != self.controller["pid"]:
            require(parent["pid"] != actual["pid"] and parent["parent_pid"] == self.controller["pid"],
                    "Server is not an immediate child or one-launcher descendant")
            self._check_command(parent)
            _, controller = self._read(parent["parent_pid"])
            chain.append(controller)
        require(chain[-1] == self.controller, "Controller identity changed")
        younger = actual
        for ancestor in chain:
            require(ancestor["created_at"] <= younger["created_at"], "Parent creation time follows child")
            younger = ancestor
        if self.parent_chain is not None:
            require(chain == self.parent_chain, "Server parent chain changed")
        return process, chain

    @property
    def identity(self):
        return copy.deepcopy(self.expected)

    @property
    def provenance(self):
        return dict(controller_identity=copy.deepcopy(self.controller), parent_chain=copy.deepcopy(self.parent_chain),
                    command=list(self.command), allowed_executables=list(self.allowed), wrapper_path=str(WRAPPER))

    def sample_cpu(self):
        process, _ = self.verify()
        try:
            counters = process.cpu_times()
            stamp = time.perf_counter()
            require(process.is_running(), "Server exited during CPU sample")
        except (psutil.Error, OSError) as exc:
            raise RuntimeError("Server CPU counters unavailable") from exc
        require(all(math.isfinite(v) and v >= 0 for v in (counters.user, counters.system)), "Invalid server CPU counters")
        return dict(identity=self.identity, user_seconds=counters.user, system_seconds=counters.system,
                    monotonic_seconds=stamp)


class ObserverAdapter(Adapter):
    def __init__(self, session, verifier):
        super().__init__(session)
        self._verifier = verifier

    @property
    def server_identity(self):
        return self._verifier.identity

    @property
    def server_launch_provenance(self):
        return self._verifier.provenance

    def sample_server_cpu(self):
        return self._verifier.sample_cpu()


async def wait_handshake(path, timeout=10.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            # The file is created exclusively; allow a writer's short partial JSON.
            await asyncio.sleep(0.02)
    raise RuntimeError("MCP identity handshake did not complete")


async def run_observer(scenario, output_directory, *args, **kwargs):
    """Run one persistent real MCP session; never call a game tool implicitly."""
    require("client" not in kwargs, "run_observer supplies client")
    directory = Path(output_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    identity_path = directory / "mcp-server-identity.json"
    log_path = directory / "mcp-server.stderr.log"
    require(not identity_path.exists(), "Refusing existing identity handshake")
    token = secrets.token_hex(32)
    command = [sys.executable, str(WRAPPER), "--identity", str(identity_path), "--token", token]
    allowed = sorted({str(Path(sys.executable).resolve()), str(Path(sys._base_executable).resolve())})
    controller = process_identity(psutil.Process())
    params = StdioServerParameters(command=command[0], args=command[1:], cwd=str(ROOT))
    # The library owns only this newly spawned stdio process/tree and performs its
    # EOF/timeout cleanup. No process scan, watchdog access or manual kill exists.
    with log_path.open("x", encoding="utf-8") as log:
        async with stdio_client(params, errlog=log) as (read, write):
            payload = await wait_handshake(identity_path)
            verifier = ServerIdentityVerifier(payload, token=token, command=command,
                controller_identity=controller, allowed_executables=allowed)
            async with ClientSession(read, write) as session:
                await session.initialize()
                registered = await session.list_tools()
                names = {tool.name for tool in registered.tools}
                require(len(names) == len(registered.tools) and {"get_frame_stats", "heartbeat", "ping"} <= names,
                        "Unexpected observer MCP registry")
                verifier.verify()
                return await scenario(*args, client=ObserverAdapter(session, verifier), **kwargs)
