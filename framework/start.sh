#!/bin/bash
# 高并发订单监控系统启动脚本 (Linux/Mac)
# 使用方法: ./start.sh [start|stop|restart|status|test|install|help]

set -e

# 设置项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 设置虚拟环境路径
VENV_PATH="$PROJECT_ROOT/.venv"
PYTHON_EXE="$VENV_PATH/bin/python"
PID_FILE="$PROJECT_ROOT/app.pid"
LOG_FILE="$PROJECT_ROOT/logs/system.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查虚拟环境
check_venv() {
    if [ ! -f "$PYTHON_EXE" ]; then
        print_error "虚拟环境不存在，请先运行: python setup.py"
        print_info "或手动创建虚拟环境: python -m venv .venv"
        exit 1
    fi
}

# 检查主应用文件
check_app() {
    if [ ! -f "$PROJECT_ROOT/app.py" ]; then
        print_error "app.py 文件不存在"
        exit 1
    fi
}

# 获取进程ID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

# 检查进程是否运行
is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# 启动系统
start_system() {
    print_info "启动订单监控系统..."
    
    if is_running; then
        print_warning "系统已在运行 (PID: $(get_pid))"
        return 0
    fi
    
    # 确保日志目录存在
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # 激活虚拟环境并启动应用
    source "$VENV_PATH/bin/activate"
    print_info "虚拟环境已激活"
    
    print_info "启动应用..."
    
    # 后台启动应用
    nohup "$PYTHON_EXE" app.py start > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # 保存PID
    echo $pid > "$PID_FILE"
    
    # 等待一下确保启动成功
    sleep 2
    
    if is_running; then
        print_success "系统启动成功 (PID: $pid)"
        print_info "日志文件: $LOG_FILE"
    else
        print_error "系统启动失败"
        if [ -f "$LOG_FILE" ]; then
            print_info "查看日志: tail -f $LOG_FILE"
        fi
        exit 1
    fi
}

# 停止系统
stop_system() {
    print_info "停止订单监控系统..."
    
    if ! is_running; then
        print_warning "系统未运行"
        # 清理PID文件
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
        return 0
    fi
    
    local pid=$(get_pid)
    print_info "终止进程 (PID: $pid)..."
    
    # 发送TERM信号
    kill -TERM "$pid" 2>/dev/null || true
    
    # 等待进程结束
    local count=0
    while is_running && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    # 如果还在运行，强制终止
    if is_running; then
        print_warning "进程未响应，强制终止..."
        kill -KILL "$pid" 2>/dev/null || true
        sleep 1
    fi
    
    # 清理PID文件
    [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    
    if is_running; then
        print_error "无法停止系统"
        exit 1
    else
        print_success "系统已停止"
    fi
}

# 重启系统
restart_system() {
    print_info "重启订单监控系统..."
    stop_system
    sleep 2
    start_system
}

# 查看状态
show_status() {
    print_info "检查系统状态..."
    
    if is_running; then
        local pid=$(get_pid)
        print_success "系统正在运行 (PID: $pid)"
        
        # 显示进程信息
        if command -v ps >/dev/null 2>&1; then
            print_info "进程信息:"
            ps -p "$pid" -o pid,ppid,cmd,etime,pcpu,pmem 2>/dev/null || true
        fi
        
        # 显示端口占用（如果有的话）
        if command -v netstat >/dev/null 2>&1; then
            print_info "端口占用:"
            netstat -tlnp 2>/dev/null | grep "$pid" || print_info "无端口占用"
        fi
        
    else
        print_warning "系统未运行"
    fi
    
    # 运行应用状态检查
    if [ -f "$PYTHON_EXE" ]; then
        source "$VENV_PATH/bin/activate"
        "$PYTHON_EXE" app.py status 2>/dev/null || true
    fi
}

# 运行测试
run_test() {
    print_info "运行系统测试..."
    
    check_venv
    check_app
    
    source "$VENV_PATH/bin/activate"
    
    if "$PYTHON_EXE" app.py test; then
        print_success "系统测试通过"
    else
        print_error "系统测试失败"
        exit 1
    fi
}

# 安装依赖
install_deps() {
    print_info "安装系统依赖..."
    python setup.py
}

# 显示日志
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_info "显示系统日志 (按 Ctrl+C 退出):"
        tail -f "$LOG_FILE"
    else
        print_warning "日志文件不存在: $LOG_FILE"
    fi
}

# 显示帮助
show_help() {
    echo
    echo "高并发订单监控系统管理脚本"
    echo
    echo "用法: $0 [命令]"
    echo
    echo "可用命令:"
    echo "  start     - 启动订单监控系统"
    echo "  stop      - 停止订单监控系统"
    echo "  restart   - 重启订单监控系统"
    echo "  status    - 查看系统状态"
    echo "  test      - 运行系统测试"
    echo "  install   - 安装系统依赖"
    echo "  logs      - 显示系统日志"
    echo "  help      - 显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0 start    # 启动系统"
    echo "  $0 status   # 查看状态"
    echo "  $0 logs     # 查看日志"
    echo "  $0 test     # 运行测试"
    echo
}

# 主函数
main() {
    local command=${1:-start}
    
    echo "================================================"
    echo "高并发订单监控系统管理脚本"
    echo "================================================"
    
    case "$command" in
        start)
            check_venv
            check_app
            start_system
            ;;
        stop)
            stop_system
            ;;
        restart)
            check_venv
            check_app
            restart_system
            ;;
        status)
            show_status
            ;;
        test)
            run_test
            ;;
        install)
            install_deps
            ;;
        logs)
            show_logs
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"