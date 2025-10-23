@echo off
REM 高并发订单监控系统启动脚本 (Windows)
REM 使用方法: start.bat [start|stop|restart|status|test]

setlocal enabledelayedexpansion

REM 设置项目根目录
set PROJECT_ROOT=%~dp0
cd /d "%PROJECT_ROOT%"

REM 设置虚拟环境路径
set VENV_PATH=%PROJECT_ROOT%.venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
set PID_FILE=%PROJECT_ROOT%app.pid

REM 检查虚拟环境是否存在
if not exist "%PYTHON_EXE%" (
    echo 错误: 虚拟环境不存在，请先运行 python setup.py
    echo 或手动创建虚拟环境: python -m venv .venv
    pause
    exit /b 1
)

REM 检查主应用文件是否存在
if not exist "%PROJECT_ROOT%app.py" (
    echo 错误: app.py 文件不存在
    pause
    exit /b 1
)

REM 获取命令参数
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=start

echo ================================================
echo 高并发订单监控系统管理脚本
echo ================================================

REM 根据命令执行相应操作
if /i "%COMMAND%"=="start" goto :start
if /i "%COMMAND%"=="stop" goto :stop
if /i "%COMMAND%"=="restart" goto :restart
if /i "%COMMAND%"=="status" goto :status
if /i "%COMMAND%"=="test" goto :test
if /i "%COMMAND%"=="install" goto :install
if /i "%COMMAND%"=="help" goto :help

echo 未知命令: %COMMAND%
goto :help

:start
echo 启动订单监控系统...
echo.

REM 检查是否已经在运行
if exist "%PID_FILE%" (
    echo 系统可能已在运行，检查进程...
    REM 这里可以添加进程检查逻辑
)

REM 激活虚拟环境并启动应用
call "%VENV_PATH%\Scripts\activate.bat"
echo 虚拟环境已激活

echo 启动应用...
"%PYTHON_EXE%" app.py start

goto :end

:stop
echo 停止订单监控系统...
echo.

REM 查找并终止Python进程（简化版本）
tasklist /fi "imagename eq python.exe" /fo table | find /i "python.exe" > nul
if %errorlevel% equ 0 (
    echo 发现Python进程，尝试终止...
    REM 这里应该更精确地识别我们的应用进程
    echo 请手动终止应用进程或使用 Ctrl+C
) else (
    echo 没有发现运行中的Python进程
)

REM 删除PID文件
if exist "%PID_FILE%" del "%PID_FILE%"

goto :end

:restart
echo 重启订单监控系统...
echo.
call :stop
timeout /t 3 /nobreak > nul
call :start
goto :end

:status
echo 检查系统状态...
echo.

call "%VENV_PATH%\Scripts\activate.bat"
"%PYTHON_EXE%" app.py status

goto :end

:test
echo 运行系统测试...
echo.

call "%VENV_PATH%\Scripts\activate.bat"
"%PYTHON_EXE%" app.py test

if %errorlevel% equ 0 (
    echo.
    echo ✓ 系统测试通过
) else (
    echo.
    echo ✗ 系统测试失败
)

goto :end

:install
echo 安装系统依赖...
echo.

python setup.py

goto :end

:help
echo.
echo 用法: start.bat [命令]
echo.
echo 可用命令:
echo   start     - 启动订单监控系统
echo   stop      - 停止订单监控系统
echo   restart   - 重启订单监控系统
echo   status    - 查看系统状态
echo   test      - 运行系统测试
echo   install   - 安装系统依赖
echo   help      - 显示此帮助信息
echo.
echo 示例:
echo   start.bat start    # 启动系统
echo   start.bat status   # 查看状态
echo   start.bat test     # 运行测试
echo.

:end
echo.
echo 操作完成
pause