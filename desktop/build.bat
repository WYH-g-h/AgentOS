@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 🚀 开始打包 AgentOS...

echo 🧹 清理虚拟环境...
cd ..\.venv
for /d /r . %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc >nul 2>&1
cd ..\desktop

echo 📦 构建前端...
cd ..\web
call npm run build
if errorlevel 1 (
    echo ❌ 前端构建失败
    pause
    exit /b 1
)

echo 📦 打包 Electron...
cd ..\desktop
call npx electron-packager . AgentOS --platform=win32 --arch=x64 --out=dist --overwrite --extra-resource="../api" --extra-resource="../core" --extra-resource="../models" --extra-resource="../tools" --extra-resource="../skills" --extra-resource="../workflows" --extra-resource="../config" --extra-resource="../.venv" --extra-resource="../desktop/assets"

if errorlevel 1 (
    echo ❌ Electron 打包失败
    pause
    exit /b 1
)

echo 📦 复制前端文件...
if not exist dist\AgentOS-win32-x64\resources\web\dist mkdir dist\AgentOS-win32-x64\resources\web\dist
xcopy /E /I /Y ..\web\dist dist\AgentOS-win32-x64\resources\web\dist

echo ✅ 打包完成！
echo 📁 输出: dist\AgentOS-win32-x64\AgentOS.exe
pause