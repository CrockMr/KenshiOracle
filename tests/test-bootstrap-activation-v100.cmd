@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /O2 /EHsc /MD /W3 "%~dp0test_bootstrap_activation.cpp" /Fo"%~dp0..\plugin\build\native-tests\test_bootstrap_activation.obj" /Fe"%~dp0..\plugin\build\native-tests\test_bootstrap_activation.exe"
if errorlevel 1 exit /b %errorlevel%
"%~dp0..\plugin\build\native-tests\test_bootstrap_activation.exe"
exit /b %errorlevel%
