@echo off
REM Start Microsoft Edge with remote debugging enabled
REM This allows the agent to connect to your existing browser

echo Starting Edge with remote debugging on port 9222...
start msedge.exe --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Microsoft\Edge\User Data"

echo.
echo Edge started with remote debugging!
echo The agent can now connect to your existing browser.
echo.
echo Keep this window open while using the agent.
pause
