@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 🚀 开始清理 AgentOS 分发版...
echo.

echo 🧹 清理 resources 中的 Python 字节码...
if exist dist\AgentOS-win32-x64\resources (
    for /d /r dist\AgentOS-win32-x64\resources %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
    del /s /q dist\AgentOS-win32-x64\resources\*.pyc >nul 2>&1
    echo   ✅ 已清理 Python 字节码
)

echo 🧹 清理测试数据...
if exist dist\AgentOS-win32-x64\resources\data (
    rmdir /s /q dist\AgentOS-win32-x64\resources\data
    echo   ✅ 已删除测试 data
)
if exist dist\AgentOS-win32-x64\resources\output (
    rmdir /s /q dist\AgentOS-win32-x64\resources\output
    echo   ✅ 已删除测试 output
)

echo 🔑 清空 API Key...
if exist dist\AgentOS-win32-x64\resources\config\config.yaml (
    powershell -Command "(Get-Content dist\AgentOS-win32-x64\resources\config\config.yaml) -replace 'api_key:.*', 'api_key: ''' | Set-Content dist\AgentOS-win32-x64\resources\config\config.yaml"
    echo   ✅ 已清空 API Key
)

echo 🧹 清理虚拟环境字节码（如果有）...
if exist dist\AgentOS-win32-x64\resources\.venv (
    for /d /r dist\AgentOS-win32-x64\resources\.venv %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
    del /s /q dist\AgentOS-win32-x64\resources\.venv\*.pyc >nul 2>&1
    echo   ✅ 已清理 .venv 字节码
)

echo 📦 计算最终体积...
if exist dist\AgentOS-win32-x64 (
    for /f "tokens=3" %%a in ('dir /s /-c dist\AgentOS-win32-x64 2^>nul ^| find "个文件"') do set SIZE=%%a
    echo   ✅ 总大小: %SIZE% bytes
)

echo.
echo ✅ 清理完成！
echo 📁 输出: dist\AgentOS-win32-x64\AgentOS.exe
echo ⚠️ 提醒: 分发前请测试 AgentOS.exe 是否正常！
pause