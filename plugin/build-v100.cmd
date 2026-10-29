@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64
if errorlevel 1 exit /b %errorlevel%
set "KENSHILIB_DIR=%~dp0..\references\KenshiLib_Examples_deps\KenshiLib"
set "BOOST_INCLUDE_PATH=%~dp0..\references\KenshiLib_Examples_deps\boost_1_60_0"
set "VCTargetsPath=C:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\"
set "PROBE_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PROBE_PYTHON%" set "PROBE_PYTHON=python"
"%PROBE_PYTHON%" "%~dp0prepare_deps.py"
if errorlevel 1 exit /b %errorlevel%
"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" "%~dp0KenshiProbe.vcxproj" /p:Configuration=Release /p:Platform=x64 /verbosity:minimal /nologo
if errorlevel 1 exit /b %errorlevel%
"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" "%~dp0KenshiProbeBootstrap.vcxproj" /p:Configuration=Release /p:Platform=x64 /verbosity:minimal /nologo
exit /b %errorlevel%
