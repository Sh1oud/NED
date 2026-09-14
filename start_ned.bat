@echo off
setlocal
title NED 启动器

cd /d "%~dp0"

echo.
echo [ NED 启动器 ] 正在确认项目目录...
if not exist "pyproject.toml" goto :not_project_root
if not exist "ned\app\cli.py" goto :not_project_root

echo [ NED 启动器 ] 正在检查 Python 环境...
where py >nul 2>nul
if not errorlevel 1 (
    set "NED_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto :python_missing
    set "NED_PYTHON=python"
)

echo [ NED 启动器 ] 正在安装 NED（首次运行可能需要一点时间）...
%NED_PYTHON% -m pip install -e .
if errorlevel 1 goto :install_failed

echo.
echo [ NED 启动器 ] 正在启动本地服务...
echo [ NED 启动器 ] 浏览器地址：http://127.0.0.1:8000/
echo [ NED 启动器 ] 按 Ctrl+C 可停止服务。
echo.
%NED_PYTHON% -m ned.app.cli serve
set "NED_EXIT_CODE=%errorlevel%"

echo.
echo [ NED 启动器 ] 服务已停止（退出代码：%NED_EXIT_CODE%）。
pause
exit /b %NED_EXIT_CODE%

:not_project_root
echo.
echo [ 错误 ] 未找到 NED 项目文件。请将 start_ned.bat 放在项目根目录后再运行。
pause
exit /b 1

:python_missing
echo.
echo [ 错误 ] 未找到 Python。请先安装 Python 3.12+，然后重新双击此文件。
pause
exit /b 1

:install_failed
echo.
echo [ 错误 ] NED 安装失败。请检查网络、Python 版本和终端中的错误信息后重试。
pause
exit /b 1
