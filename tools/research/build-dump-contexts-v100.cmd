@echo off
setlocal
call "%~dp0..\..\plugin\v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\..\plugin\build\native-tests" mkdir "%~dp0..\..\plugin\build\native-tests"
cl /nologo /EHsc /MD /W3 "%~dp0dump_contexts.cpp" /Fo"%~dp0..\..\plugin\build\native-tests\dump_contexts.obj" /Fe"%~dp0..\..\plugin\build\native-tests\dump_contexts.exe"
exit /b %errorlevel%
