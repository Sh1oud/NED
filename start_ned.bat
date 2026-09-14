@echo off
rem ===================================================================
rem  NED launcher for Windows  (double-click after extracting the ZIP)
rem
rem  Flow: detect Python 3.12+ -> prepare .venv -> pip install -e . -> ned serve
rem
rem  ENCODING NOTES -- please do not "fix" the following:
rem    * This file is saved as GBK/cp936 with CRLF line endings.
rem      cmd.exe mis-parses LF-only batch files (goto, blocks and multibyte
rem      text break), which is why .gitattributes marks *.bat as "-text" so the
rem      bytes stored in git -- and inside GitHub's "Download ZIP" -- stay CRLF.
rem    * No chcp call: switching the codepage inside a batch file makes cmd.exe
rem      mis-split non-ASCII lines and execute fragments of them.
rem    * On a Chinese Windows console (cp936) the Chinese messages below are
rem      readable. On other console codepages they appear as mojibake, but the
rem      script still works: every command, label and check here is ASCII, and
rem      each message also carries an ASCII marker such as [ ERROR ].
rem ===================================================================
setlocal EnableExtensions
title NED 启动器

rem ---------- 0. must run from the project root ----------
cd /d "%~dp0"
if not exist "pyproject.toml" goto :err_not_project
if not exist "ned\app\cli.py" goto :err_not_project
echo.
echo [ NED ] 项目目录：%CD%
echo [ NED ] 正在检查 Python 环境...

rem ---------- 1. find a Python 3.12+ that actually works ----------
rem Having py.exe does NOT mean "py -3" works, and "python" may be the Microsoft
rem Store placeholder (which prints nothing). So we validate the *output* of
rem --version instead of trusting the exit code.
set "NED_PY="
set "NED_VER="

for /f "tokens=1,2" %%A in ('py -3 --version 2^>nul') do set "NED_VER=%%A %%B"
if not defined NED_VER goto :try_python_cmd
echo %NED_VER%| findstr /b /c:"Python 3." >nul
if errorlevel 1 goto :try_python_cmd
set "NED_PY=py -3"
goto :python_found

:try_python_cmd
set "NED_VER="
for /f "tokens=1,2" %%A in ('python --version 2^>nul') do set "NED_VER=%%A %%B"
if not defined NED_VER goto :err_no_python
echo %NED_VER%| findstr /b /c:"Python 3." >nul
if errorlevel 1 goto :err_no_python
set "NED_PY=python"

:python_found
for /f "tokens=2" %%V in ("%NED_VER%") do set "NED_PY_VER=%%V"
for /f "tokens=1 delims=." %%X in ("%NED_PY_VER%") do set "NED_PY_MAJOR=%%X"
for /f "tokens=2 delims=." %%Y in ("%NED_PY_VER%") do set "NED_PY_MINOR=%%Y"
if not "%NED_PY_MAJOR%"=="3" goto :err_py_too_old
if %NED_PY_MINOR% LSS 12 goto :err_py_too_old
echo [ NED ] 已找到 Python %NED_PY_VER%（调用方式：%NED_PY%）

rem ---------- 2. local virtualenv + editable install ----------
set "NED_VENV=%~dp0.venv"
set "NED_VPY=%NED_VENV%\Scripts\python.exe"
set "NED_CLI=%NED_VENV%\Scripts\ned.exe"

if not exist "%NED_VPY%" goto :install_package
"%NED_VPY%" -c "import ned" >nul 2>nul
if errorlevel 1 goto :install_package
if not exist "%NED_CLI%" goto :install_package
"%NED_CLI%" version >nul 2>nul
if errorlevel 1 goto :install_package
echo [ NED ] 已安装且可用，跳过安装步骤。
goto :launch

:install_package
if exist "%NED_VPY%" goto :do_install
echo [ NED ] 首次运行：正在创建本地虚拟环境 .venv（只需一次）...
%NED_PY% -m venv "%NED_VENV%"
if not exist "%NED_VPY%" goto :err_venv_failed

:do_install
echo [ NED ] 正在安装 NED：pip install -e .（首次需要联网，可能要几分钟）...
"%NED_VPY%" -m pip install --disable-pip-version-check -e "%~dp0."
if errorlevel 1 goto :err_install_failed
if not exist "%NED_CLI%" goto :err_launcher_missing

rem ---------- 3. start the project CLI: ned serve ----------
:launch
echo.
echo [ NED ] 正在启动 NED 本地服务...
echo [ NED ] 浏览器地址：http://127.0.0.1:8000/
echo [ NED ] 关闭本窗口或按 Ctrl+C 即可停止服务。
echo.
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000/"
"%NED_CLI%" serve
set "NED_EXIT=%errorlevel%"
echo.
echo [ NED ] 服务已停止（退出代码：%NED_EXIT%）。
if not "%NED_EXIT%"=="0" echo [ NED ] 提示：可改用 "%NED_VPY%" -m ned.app.cli serve 重试。
pause
exit /b %NED_EXIT%

rem ---------- error branches: every one of them pauses ----------
:err_not_project
echo.
echo [ ERROR ] 未找到 NED 项目文件。
echo           请确认 start_ned.bat 与 pyproject.toml 在同一个文件夹内，
echo           并且是先把 ZIP 完整解压再运行（不要在压缩包预览窗口里双击）。
pause
exit /b 1

:err_no_python
echo.
echo [ ERROR ] 未找到可用的 Python 3。
echo           1. 请安装 Python 3.12 或更高版本：
echo              https://www.python.org/downloads/windows/
echo              安装时务必勾选 Add python.exe to PATH。
echo           2. 如果已经装过还是报这个错，可能是 Microsoft Store 的占位程序：
echo              打开 设置 - 应用 - 高级应用设置 - 应用执行别名，
echo              关闭 python.exe 与 python3.exe 这两个别名后重试。
echo           3. 装好后重新双击本文件即可。
pause
exit /b 1

:err_py_too_old
echo.
echo [ ERROR ] Python 版本过低：检测到 %NED_PY_VER%，NED 需要 3.12 或更高版本。
echo           请安装新版 Python：https://www.python.org/downloads/windows/
pause
exit /b 1

:err_venv_failed
echo.
echo [ ERROR ] 创建虚拟环境 .venv 失败。
echo           常见原因：目录没有写权限、磁盘空间不足、杀毒软件拦截。
echo           如果解压在 C:\Program Files 之类的受保护目录，请改为解压到
echo           桌面或文档等普通文件夹后重试。
echo           也可以手动执行：%NED_PY% -m venv "%~dp0.venv"
pause
exit /b 1

:err_install_failed
echo.
echo [ ERROR ] NED 安装失败（pip install -e . 返回了错误，请往上翻看具体信息）。
echo           常见原因：网络不通、公司代理、Python 安装缺少 pip。
echo           可手动重试：
echo              cd /d "%~dp0"
echo              .venv\Scripts\python.exe -m pip install -e .
pause
exit /b 1

:err_launcher_missing
echo.
echo [ ERROR ] 安装完成，但没有找到启动器 .venv\Scripts\ned.exe。
echo           请删除 .venv 文件夹后重新双击本文件。
pause
exit /b 1
