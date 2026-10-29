"""Identity/CPU guards and real stdio handshake; never invoke a game tool."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

import observer_mcp_server as bootstrap
import observer_mcp_transport as transport


class FakeProcess:
    def __init__(self, record, counter_calls):
        self.record = record
        self.pid = record["pid"]
        self.created = record["created_at"]
        self.counter_calls = counter_calls

    def create_time(self):
        return self.record["created_at"]

    def exe(self):
        return self.record["executable"]

    def cmdline(self):
        return list(self.record["cmdline"])

    def ppid(self):
        return self.record["parent_pid"]

    def is_running(self):
        return self.record.get("alive", True) and self.record["created_at"] == self.created

    def cpu_times(self):
        self.counter_calls.append(self.pid)
        if self.record.get("counter_exit"):
            raise psutil.NoSuchProcess(self.pid)
        if self.record.get("counter_reuse"):
            self.record["created_at"] += 10
        return SimpleNamespace(user=1.25, system=0.75)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "executable_path", lambda process: process.exe())
    runtime, launcher = str(tmp_path / "base-python.exe"), str(tmp_path / "venv-python.exe")
    token = "a" * 64
    command = [launcher, str(transport.WRAPPER), "--identity", str(tmp_path / "identity.json"), "--token", token]
    controller = dict(pid=100, created_at=1.0, executable=runtime, cmdline=[runtime, "controller.py"], parent_pid=50)
    records = {
        100: controller,
        200: dict(pid=200, created_at=2.0, executable=launcher, cmdline=command, parent_pid=100),
        300: dict(pid=300, created_at=3.0, executable=runtime, cmdline=[runtime, *command[1:]], parent_pid=200),
    }
    looked_up, counters = [], []
    def factory(pid):
        looked_up.append(pid)
        if pid not in records:
            raise psutil.NoSuchProcess(pid)
        return FakeProcess(records[pid], counters)
    def verifier(direct=False, payload=None):
        if direct:
            records[300]["parent_pid"] = 100
        if payload is None:
            payload = dict(protocol=bootstrap.HANDSHAKE_PROTOCOL, identity=dict(records[300], token=token))
        return transport.ServerIdentityVerifier(payload, token=token, command=command,
            controller_identity=controller, allowed_executables=[runtime, launcher], process_factory=factory)
    return SimpleNamespace(records=records, looked_up=looked_up, counters=counters, verifier=verifier,
                           token=token, command=command, controller=controller)


@pytest.mark.parametrize("direct", [True, False])
def test_verified_cpu_and_provenance(environment, monkeypatch, direct):
    env = environment
    verifier = env.verifier(direct)
    monkeypatch.setattr(transport.time, "perf_counter", lambda: 432.5)
    sample = verifier.sample_cpu()
    assert sample == dict(identity=verifier.identity, user_seconds=1.25, system_seconds=.75,
                          monotonic_seconds=432.5)
    assert [row["pid"] for row in verifier.provenance["parent_chain"]] == ([100] if direct else [200, 100])
    assert set(env.looked_up) == ({100, 300} if direct else {100, 200, 300})
    assert env.counters == [300]
    altered = verifier.identity
    altered["cmdline"].clear()
    assert verifier.sample_cpu()["identity"] == sample["identity"]  # No mutable identity escape.


@pytest.mark.parametrize("change", ["token", "protocol", "pid", "created_at", "command", "executable"])
def test_forged_handshake_rejected(environment, change):
    env = environment
    payload = dict(protocol=bootstrap.HANDSHAKE_PROTOCOL, identity=dict(env.records[300], token=env.token))
    if change == "token":
        payload["identity"]["token"] = "b" * 64
    elif change == "protocol":
        payload["protocol"] = "wrong"
    elif change == "pid":
        payload["identity"]["pid"] = 100
    elif change == "created_at":
        payload["identity"]["created_at"] += .5
    elif change == "command":
        payload["identity"]["cmdline"] = ["different.exe"]
    else:
        payload["identity"]["executable"] = str(Path(env.records[300]["executable"]).parent / "different.exe")
    with pytest.raises(RuntimeError):
        env.verifier(payload=payload)
    assert not env.counters


@pytest.mark.parametrize("pid,field,value", [(300, "created_at", 4.0), (200, "created_at", 2.5),
    (100, "created_at", 1.5), (300, "alive", False), (300, "parent_pid", 999),
    (200, "cmdline", ["foreign.py"]), (100, "cmdline", ["replaced-controller.py"])])
def test_replacement_exit_or_parent_change_rejected_before_cpu(environment, pid, field, value):
    env = environment
    verifier = env.verifier()
    env.records[pid][field] = value
    with pytest.raises(RuntimeError):
        verifier.sample_cpu()
    assert not env.counters


@pytest.mark.parametrize("field", ["counter_exit", "counter_reuse"])
def test_exit_or_pid_reuse_during_counter_rejected(environment, field):
    verifier = environment.verifier()
    environment.records[300][field] = True
    with pytest.raises(RuntimeError):
        verifier.sample_cpu()


def test_no_scan_or_arbitrary_ancestor_traversal(environment):
    environment.records[200]["parent_pid"] = 999
    with pytest.raises(RuntimeError, match="one-launcher"):
        environment.verifier()
    assert set(environment.looked_up) == {200, 300}


def test_server_publication_is_exclusive(tmp_path, monkeypatch):
    expected = dict(pid=123, created_at=4.5, executable=str(tmp_path / "python.exe"),
                    cmdline=["python.exe", "observer_mcp_server.py"], parent_pid=100)
    monkeypatch.setattr(bootstrap, "process_identity", lambda _: expected)
    path = tmp_path / "identity.json"
    identity = bootstrap.publish_identity(path, "a" * 64)
    original = path.read_bytes()
    assert json.loads(original) == dict(protocol=bootstrap.HANDSHAKE_PROTOCOL, identity=identity)
    with pytest.raises(FileExistsError):
        bootstrap.publish_identity(path, "b" * 64)
    assert path.read_bytes() == original


def test_partial_handshake_then_timeout(tmp_path):
    path = tmp_path / "identity.json"
    async def check():
        path.write_text("{", encoding="utf-8")
        with pytest.raises(RuntimeError, match="did not complete"):
            await transport.wait_handshake(path, timeout=.02)
        expected = dict(protocol=bootstrap.HANDSHAKE_PROTOCOL)
        path.write_text(json.dumps(expected), encoding="utf-8")
        assert await transport.wait_handshake(path) == expected
    asyncio.run(check())


def test_existing_logs_refused_before_spawn(tmp_path, monkeypatch):
    path = tmp_path / "mcp-server.stderr.log"
    path.write_text("historical proof", encoding="utf-8")
    def no_spawn(*args, **kwargs):
        pytest.fail("existing log must refuse before spawning")
    monkeypatch.setattr(transport, "stdio_client", no_spawn)
    async def scenario(*, client):
        pytest.fail("no scenario expected")
    with pytest.raises(FileExistsError):
        asyncio.run(transport.run_observer(scenario, tmp_path))
    assert path.read_text(encoding="utf-8") == "historical proof"


def test_real_stdio_registry_handshake_cpu_and_cleanup_without_game(tmp_path):
    async def scenario(value, *, client, suffix):
        before = client.sample_server_cpu()
        # initialize/list_tools occur in the transport; no tool is ever called.
        await asyncio.sleep(.02)
        after = client.sample_server_cpu()
        assert before["identity"] == after["identity"] == client.server_identity
        assert after["monotonic_seconds"] >= before["monotonic_seconds"]
        assert after["user_seconds"] >= before["user_seconds"]
        assert after["system_seconds"] >= before["system_seconds"]
        return dict(value=value + suffix, identity=client.server_identity,
                    provenance=client.server_launch_provenance)
    result = asyncio.run(transport.run_observer(scenario, tmp_path, "stdio", suffix="-only"))
    assert result["value"] == "stdio-only"
    payload = json.loads((tmp_path / "mcp-server-identity.json").read_text(encoding="utf-8"))
    assert payload["identity"] == result["identity"]
    assert (tmp_path / "mcp-server.stderr.log").is_file()
    try:
        process = psutil.Process(result["identity"]["pid"])
    except psutil.NoSuchProcess:
        pass
    else:
        assert process.create_time() != result["identity"]["created_at"] or not process.is_running()

