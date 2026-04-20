@echo off
REM ═══════════════════════════════════════════════
REM  凌策專案 — 打包接續包（一鍵產生 zip）
REM ═══════════════════════════════════════════════
setlocal enabledelayedexpansion

set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%
set TIMESTAMP=%TIMESTAMP: =0%
set OUT=lingce_handoff_%TIMESTAMP%.zip
set STAGE=%TEMP%\lingce_handoff_stage

echo.
echo ================================================
echo  凌策專案接續包製作
echo ================================================
echo.

REM 清除舊暫存
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\lingce-company"
mkdir "%STAGE%\reference_docs"
mkdir "%STAGE%\10CSVfile"

echo [1/4] 複製專案主體...
xcopy /E /I /Q /Y ".\" "%STAGE%\lingce-company\" ^
  /EXCLUDE:.\.handoff_exclude.txt 2>nul

REM 若排除清單不存在，改為手動過濾
if not exist ".\.handoff_exclude.txt" (
  xcopy /E /I /Q /Y ".\*" "%STAGE%\lingce-company\"
  REM 清除不需要的檔案
  if exist "%STAGE%\lingce-company\node_modules" rmdir /s /q "%STAGE%\lingce-company\node_modules"
  if exist "%STAGE%\lingce-company\__pycache__" rmdir /s /q "%STAGE%\lingce-company\__pycache__"
  if exist "%STAGE%\lingce-company\src\backend\__pycache__" rmdir /s /q "%STAGE%\lingce-company\src\backend\__pycache__"
  if exist "%STAGE%\lingce-company\chroma_kb" rmdir /s /q "%STAGE%\lingce-company\chroma_kb"
)

echo [2/4] 複製測試 CSV 資料...
if exist "C:\Users\B00325\Desktop\10CSVfile\" (
  xcopy /E /I /Q /Y "C:\Users\B00325\Desktop\10CSVfile\*" "%STAGE%\10CSVfile\"
) else (
  echo    ^(10CSVfile 不存在，跳過^)
)

echo [3/4] 複製參考文件 (addwii / microjet docx)...
copy /Y "C:\Users\B00325\Desktop\addwii_驗收評比標準_含測試題目v3.docx" "%STAGE%\reference_docs\" 2>nul
copy /Y "C:\Users\B00325\Desktop\microjet_驗收標準_v0.3_1.docx" "%STAGE%\reference_docs\" 2>nul
copy /Y "C:\Users\B00325\Desktop\addwii_AI智能平台_開發文件v1.1初稿.docx" "%STAGE%\reference_docs\" 2>nul
copy /Y "C:\Users\B00325\AppData\Local\Temp\凌策系統開發文件.docx" "%STAGE%\reference_docs\" 2>nul
copy /Y "C:\Users\B00325\AppData\Local\Temp\凌策公司簡報.pptx" "%STAGE%\reference_docs\" 2>nul

echo [4/4] 壓縮成 zip...
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%cd%\%OUT%' -Force"

rmdir /s /q "%STAGE%"

echo.
echo ================================================
echo   完成！
echo   輸出檔案：%cd%\%OUT%
echo ================================================
echo.
echo 下一步：
echo   1. 把 %OUT% 複製到新機器（USB / 網路磁碟 / 雲端）
echo   2. 解壓縮後先讀 lingce-company\HANDOFF.md
echo   3. 按照 HANDOFF.md 的「新機器啟動流程」設定環境
echo.
pause
