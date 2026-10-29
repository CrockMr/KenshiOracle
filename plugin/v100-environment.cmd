@echo off
rem Called by build/test scripts; the caller owns setlocal.
if not defined KENSHI_VCVARSALL (
  echo Set KENSHI_VCVARSALL to the VC2010 vcvarsall.bat file. See docs/first-run.md. 1>&2
  exit /b 2
)
if not exist "%KENSHI_VCVARSALL%" (
  echo KENSHI_VCVARSALL does not identify an existing file. 1>&2
  exit /b 2
)
call "%KENSHI_VCVARSALL%" amd64
if errorlevel 1 exit /b %errorlevel%
if defined KENSHI_VC_TARGETS (
  if not exist "%KENSHI_VC_TARGETS%\Microsoft.Cpp.Default.props" (
    echo KENSHI_VC_TARGETS must contain Microsoft.Cpp.Default.props. 1>&2
    exit /b 2
  )
  for %%I in ("%KENSHI_VC_TARGETS%") do set "VCTargetsPath=%%~fI\"
)
exit /b 0
