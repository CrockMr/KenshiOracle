"""Publish this owned stdio server's identity, then serve the existing MCP app."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

import psutil


ROOT = Path(__file__).resolve().parents[1]
HANDSHAKE_PROTOCOL = "kenshiprobe-observer-mcp-identity-v1"


def executable_path(process):
    """Query only an explicit PID; psutil 7.2 can omit the drive on this host."""
    if os.name != "nt":
        return str(Path(process.exe()).resolve())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, process.pid)  # QUERY_LIMITED_INFORMATION only.
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        return str(Path(buffer.value).resolve())
    finally:
        kernel.CloseHandle(handle)


def process_identity(process):
    return dict(pid=process.pid, created_at=process.create_time(), executable=executable_path(process),
                cmdline=process.cmdline(), parent_pid=process.ppid())


def publish_identity(path, token):
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("Invalid handshake token")
    identity = dict(process_identity(psutil.Process()), token=token)
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(dict(protocol=HANDSHAKE_PROTOCOL, identity=identity), stream, indent=2)
        stream.write("\n")
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    # No MCP messages, game connection or stdout output before this handshake.
    publish_identity(args.identity, args.token)
    sys.path.insert(0, str(ROOT / "mcp-server"))
    from server import mcp
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
