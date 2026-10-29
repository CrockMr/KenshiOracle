@echo off
setlocal
call "%~dp0..\plugin\v100-environment.cmd"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /EHsc /MD /W3 "%~dp0test_thread_identity.cpp" /Fo"%~dp0..\plugin\build\native-tests\test_thread_identity.obj" /Fe"%~dp0..\plugin\build\native-tests\test_thread_identity.exe"
if errorlevel 1 exit /b %errorlevel%
"%~dp0..\plugin\build\native-tests\test_thread_identity.exe"
exit /b %errorlevel%
