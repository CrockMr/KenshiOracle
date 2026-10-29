@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /EHsc /MD /W3 "%~dp0dump_stacks.cpp" /Fo"%~dp0..\plugin\build\native-tests\dump_stacks.obj" /Fe"%~dp0..\plugin\build\native-tests\dump_stacks.exe"
exit /b %errorlevel%
