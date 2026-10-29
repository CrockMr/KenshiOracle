@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /O2 /EHsc /MD /W3 "%~dp0benchmark_statistics_detail.cpp" /Fo"%~dp0..\plugin\build\native-tests\benchmark_statistics_detail.obj" /Fe"%~dp0..\plugin\build\native-tests\benchmark_statistics_detail.exe"
exit /b %errorlevel%
