# Performance research tools

This directory contains the historical performance campaign's offline
analyzers, manual acquisition scripts and native synthetic benchmarks.
It also holds their thread, ETW, stack and minidump support modules. The
oracle runner, schemas, probe transport and MCP server remain in their
dedicated directories. Reusable process-resource and session-budget helpers
remain with the MCP code; their optional thread imports use a repository-relative
research path without importing Windows capture APIs at startup.

The [research archive](../../docs/research/README.md) explains the evidence.
These scripts do not run as part of an ordinary oracle scenario. Manual
`live_*.py` tools can load or alter the identified test session, and crash/freeze
tools belong only to a supervised test copy. Read each script's preconditions
and retain its restoration evidence. No manual acquisition is invoked by pytest.

## Offline use

Run from the repository root, with the documented Python dependencies installed:

```powershell
& .\.venv\Scripts\python.exe tools/research/analyze_pause_cpu.py --help
& .\.venv\Scripts\python.exe tools/research/analyze_performance_cohorts.py --help
& .\.venv\Scripts\python.exe tools/research/export_etw.py --help
```

Each moved Python module enables imports relative to the repository, so
direct execution does not depend on a private `PYTHONPATH`. Input and output
paths still follow each command's explicit arguments. Historical manifests
identify the sources used at capture time; relocating a tool does not update
or re-certify an old measurement.

## Optional native tools

The seven `benchmark-*-v100.cmd` and `build-dump-*-v100.cmd` commands call
the shared [v100 environment helper](../../plugin/v100-environment.cmd).
They write only ignored build outputs under `plugin/build/native-tests/`.
The associated C++ sources are original benchmark/debug-helper code; local
SDK headers, symbols, executables and game files are not distributed here.
Unit-test fixtures remain in `tests/`; pytest remains rooted there and
includes this directory on its import path.

Set tool locations in the environment as described in
[first-run instructions](../../docs/first-run.md):

| Variable | Purpose |
| --- | --- |
| `KENSHI_VCVARSALL` | VC2010 `vcvarsall.bat`, called for `amd64`. |
| `KENSHI_VC_TARGETS` | Optional VC2010 C++ targets directory for the shared build setup. |
| `KENSHI_XPERF` | Optional reviewed `xperf.exe`; otherwise resolved from `PATH`. |
| `KENSHI_WPR` | Optional `wpr.exe`; otherwise resolved from `PATH`. |
| `KENSHI_DBGHELP` | Reviewed x64 Windows SDK `dbghelp.dll` for stack/minidump tools. Required unless that DLL is explicitly placed in the working directory. |

DbgHelp receives local symbol/image paths only. Tool identity and hashes are
recorded by the relevant collectors. Missing tools, changed inputs or ambiguous
process identities fail explicitly; no download, administrator elevation or
symbol-server access is performed automatically.
