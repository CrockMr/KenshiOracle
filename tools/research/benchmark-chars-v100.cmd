@echo off
setlocal
call "%~dp0..\..\plugin\v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\..\plugin\build\native-tests" mkdir "%~dp0..\..\plugin\build\native-tests"
cl /nologo /O2 /EHsc /MD /W3 "%~dp0benchmark_chars_telemetry.cpp" /Fo"%~dp0..\..\plugin\build\native-tests\benchmark_chars_telemetry.obj" /Fe"%~dp0..\..\plugin\build\native-tests\benchmark_chars_telemetry.exe"
exit /b %errorlevel%
