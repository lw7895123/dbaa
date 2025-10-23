# -*- coding: utf-8 -*-
"""
高并发订单监控系统主应用
整合所有框架组件，提供统一的启动入口
"""
import sys
from framework.app import OrderMonitoringApp


def main():
    """主函数"""
    app = OrderMonitoringApp()

    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'start':
            app.run()
        elif command == 'status':
            if app.start():
                status = app.get_status()
                print("系统状态:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
                app.stop()
        elif command == 'test':
            # 测试模式：启动后立即停止
            if app.start():
                print("系统测试通过")
                app.stop()
            else:
                print("系统测试失败")
                sys.exit(1)
        else:
            print("用法: python app.py [start|status|test]")
            sys.exit(1)
    else:
        # 默认运行模式
        app.run()


if __name__ == "__main__":
    main()