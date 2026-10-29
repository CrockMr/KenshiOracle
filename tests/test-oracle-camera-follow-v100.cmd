@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\plugin\build\native-tests" mkdir "%~dp0..\plugin\build\native-tests"
cl /nologo /O2 /EHsc /MD /W3 "%~dp0test_oracle_camera_follow.cpp" /Fo"%~dp0..\plugin\build\native-tests\test_oracle_camera_follow.obj" /Fe"%~dp0..\plugin\build\native-tests\test_oracle_camera_follow.exe"
if errorlevel 1 exit /b %errorlevel%
"%~dp0..\plugin\build\native-tests\test_oracle_camera_follow.exe"
exit /b %errorlevel%
