@echo off
setlocal
call "%~dp0v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not defined KENSHI_MSBUILD (
  echo Set KENSHI_MSBUILD to MSBuild.exe. See docs/first-run.md. 1>&2
  exit /b 2
)
if not exist "%KENSHI_MSBUILD%" (
  echo KENSHI_MSBUILD does not identify an existing file. 1>&2
  exit /b 2
)
if not defined KENSHI_VC_TARGETS (
  echo Set KENSHI_VC_TARGETS to the v100 Microsoft.Cpp targets directory. 1>&2
  exit /b 2
)
if not defined KENSHILIB_DIR set "KENSHILIB_DIR=%~dp0..\references\KenshiLib_Examples_deps\KenshiLib"
if not defined BOOST_INCLUDE_PATH set "BOOST_INCLUDE_PATH=%~dp0..\references\KenshiLib_Examples_deps\boost_1_60_0"
if not defined KENSHI_PROBE_PYTHON (
  set "KENSHI_PROBE_PYTHON=%~dp0..\.venv\Scripts\python.exe"
  if not exist "%~dp0..\.venv\Scripts\python.exe" set "KENSHI_PROBE_PYTHON=python"
)
"%KENSHI_PROBE_PYTHON%" "%~dp0prepare_deps.py"
if errorlevel 1 exit /b %errorlevel%
rem build_commit: the HEAD commit only when git works and the tree has no
rem uncommitted changes (git status --porcelain is empty); otherwise the probe
rem reports "unknown" (docs/scene-setup.md).
set "KENSHI_PROBE_BUILD_COMMIT="
git -C "%~dp0.." status --porcelain >nul 2>nul
if not errorlevel 1 (
  for /f "usebackq delims=" %%C in (`git -C "%~dp0.." rev-parse HEAD 2^>nul`) do set "KENSHI_PROBE_BUILD_COMMIT=%%C"
  for /f "usebackq delims=" %%S in (`git -C "%~dp0.." status --porcelain 2^>nul`) do set "KENSHI_PROBE_BUILD_COMMIT="
)
if defined KENSHI_PROBE_BUILD_COMMIT (echo build_commit: %KENSHI_PROBE_BUILD_COMMIT%) else echo build_commit: unknown
"%KENSHI_MSBUILD%" "%~dp0KenshiProbe.vcxproj" /p:Configuration=Release /p:Platform=x64 "/p:KenshiProbeBuildCommit=%KENSHI_PROBE_BUILD_COMMIT%" /verbosity:minimal /nologo
if errorlevel 1 exit /b %errorlevel%
"%KENSHI_MSBUILD%" "%~dp0KenshiProbeBootstrap.vcxproj" /p:Configuration=Release /p:Platform=x64 /verbosity:minimal /nologo
exit /b %errorlevel%
