// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#define KENSHI_PROBE_VERSION "0.11.0"
// build-v100.cmd defines KENSHI_PROBE_BUILD_COMMIT as the bare 40-digit commit
// of a checkout without uncommitted changes; every other build reports
// "unknown" (docs/scene-setup.md, build_commit).
#define KENSHI_PROBE_STRINGIZE_(x) #x
#define KENSHI_PROBE_STRINGIZE(x) KENSHI_PROBE_STRINGIZE_(x)
#ifdef KENSHI_PROBE_BUILD_COMMIT
#define KENSHI_PROBE_BUILD_COMMIT_TEXT KENSHI_PROBE_STRINGIZE(KENSHI_PROBE_BUILD_COMMIT)
#else
#define KENSHI_PROBE_BUILD_COMMIT_TEXT "unknown"
#endif
