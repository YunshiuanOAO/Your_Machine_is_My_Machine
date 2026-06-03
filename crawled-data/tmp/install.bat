@echo off
echo 安裝網頁爬蟲所需的 Python 套件...
echo.

REM 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤: 未找到 Python，請先安裝 Python 3.8 或更高版本
    pause
    exit /b 1
)

echo Python 版本:
python --version
echo.

REM 升級 pip
echo 升級 pip...
python -m pip install --upgrade pip
echo.

REM 安裝依賴套件
echo 安裝依賴套件...
python -m pip install -r requirements.txt
echo.

REM 檢查安裝是否成功
echo 檢查安裝狀態...
python -c "import requests, bs4, pandas; print('所有套件安裝成功！')" 2>nul
if errorlevel 1 (
    echo 警告: 某些套件可能未正確安裝
) else (
    echo 套件安裝驗證通過！
)

echo.
echo 安裝完成！現在您可以使用以下命令測試爬蟲:
echo python examples.py
echo.
echo 或直接使用爬蟲:
echo python web_crawler.py https://example.com
echo.
pause
