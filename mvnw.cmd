@echo off
setlocal
set BASE_DIR=%~dp0
where mvn >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  mvn %*
  exit /b %ERRORLEVEL%
)

set WRAPPER_HOME=%USERPROFILE%\.m2\wrapper\dists\apache-maven-3.9.16
set MAVEN_BIN=%WRAPPER_HOME%\apache-maven-3.9.16\bin\mvn.cmd
if not exist "%MAVEN_BIN%" (
  if not exist "%WRAPPER_HOME%" mkdir "%WRAPPER_HOME%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$u='https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.16/apache-maven-3.9.16-bin.zip';" ^
    "$z='%WRAPPER_HOME%\apache-maven-3.9.16-bin.zip';" ^
    "Invoke-WebRequest -UseBasicParsing $u -OutFile $z;" ^
    "Expand-Archive -Force $z '%WRAPPER_HOME%'"
)
call "%MAVEN_BIN%" %*
exit /b %ERRORLEVEL%
