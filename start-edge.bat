@echo off
echo ============================================================
echo   Start Edge (DEDICATED profile) with debug port 9222
echo ============================================================
echo.
echo   This opens a NEW Edge window using a dedicated profile:
echo   wechat_sticker_uploader\edge_attach
echo.
echo   Log in to the sticker platform HERE (WeChat scan), and KEEP
echo   this window OPEN while you run the tools:
echo     python upload.py --check
echo     python upload.py --probe
echo     python upload.py
echo.
echo   The login is a session cookie, so the window must stay open.
echo.
echo   Press any key to start Edge...
pause >nul

start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="D:\AI\DSH-DESKTOP\DSH\wechat_sticker_uploader\edge_attach" "https://sticker.weixin.qq.com/"

echo.
echo   Edge started on port 9222. Log in, then run:  python upload.py --check
echo.
pause >nul
