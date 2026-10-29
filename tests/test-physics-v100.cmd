@echo off
setlocal
call "%~dp0..\plugin\v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /EHsc /MD /W3 "%~dp0test_physics.cpp" /Fo"%~dp0..\plugin\build\native-tests\test_physics.obj" /Fe"%~dp0..\plugin\build\native-tests\test_physics.exe"
if errorlevel 1 exit /b %errorlevel%
"%~dp0..\plugin\build\native-tests\test_physics.exe"
exit /b %errorlevel%
