@echo off
setlocal
call "%~dp0..\plugin\v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /O2 /EHsc /MD /W3 "%~dp0test_probe_service.cpp" /Fo"%~dp0..\plugin\build\native-tests\test_probe_service.obj" /Fe"%~dp0..\plugin\build\native-tests\test_probe_service.exe"
if errorlevel 1 exit /b %errorlevel%
"%~dp0..\plugin\build\native-tests\test_probe_service.exe"
exit /b %errorlevel%
