# -*- coding: utf-8 -*-
"""
高并发订单监控系统主应用
整合所有框架组件，提供统一的启动入口
"""
import sys
import signal
import time
import logging
from typing import Dict, Any
from datetime import datetime

from framework.database import mysql_manager, redis_manager
from framework.logging import log_manager
from framework.monitoring import monitoring_engine

class OrderMonitoringApp:
    """高并发订单监控系统主应用"""

    def __init__(self):
        """初始化应用"""
        self.running = False
        self.start_time = None

        # 组件状态
        self.components = {
            'mysql': False,
            'redis': False,
            'logging': False,
            'monitoring': False
        }

        # 设置日志
        self.logger = self._setup_logging()

        # 注册信号处理器
        self._setup_signal_handlers()

        self.logger.info("订单监控系统应用初始化完成")

    def _setup_logging(self) -> logging.Logger:
        """设置系统日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/system.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""

        def signal_handler(signum, frame):
            self.logger.info(f"接收到信号 {signum}，开始优雅关闭...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _check_dependencies(self) -> bool:
        """检查依赖项"""
        self.logger.info("检查系统依赖项...")

        try:
            # 检查MySQL连接
            self.logger.info("检查MySQL连接...")
            if not mysql_manager.initialize():
                self.logger.error("MySQL连接失败")
                return False

            # 测试MySQL连接
            with mysql_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] != 1:
                    self.logger.error("MySQL连接测试失败")
                    return False

            self.logger.info("MySQL连接正常")
            self.components['mysql'] = True

            # 检查Redis连接
            self.logger.info("检查Redis连接...")
            if not redis_manager.initialize():
                self.logger.error("Redis连接失败")
                return False

            # 测试Redis连接
            test_key = "system_test"
            redis_manager.set(test_key, "test_value", ex=10)
            if redis_manager.get(test_key) != "test_value":
                self.logger.error("Redis连接测试失败")
                return False
            redis_manager.delete(test_key)

            self.logger.info("Redis连接正常")
            self.components['redis'] = True

            self.logger.info("所有依赖项检查通过")
            return True

        except Exception as e:
            self.logger.error(f"依赖项检查失败: {e}")
            return False

    def _initialize_components(self) -> bool:
        """初始化所有组件"""
        self.logger.info("初始化系统组件...")

        try:
            # 初始化日志管理器
            self.logger.info("初始化日志管理器...")
            if not log_manager.start():
                self.logger.error("日志管理器启动失败")
                return False
            self.components['logging'] = True
            self.logger.info("日志管理器启动成功")

            # 初始化监控引擎
            self.logger.info("初始化监控引擎...")
            if not monitoring_engine.start():
                self.logger.error("监控引擎启动失败")
                return False
            self.components['monitoring'] = True
            self.logger.info("监控引擎启动成功")

            self.logger.info("所有组件初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            return False

    def _load_initial_data(self) -> None:
        """加载初始数据"""
        self.logger.info("加载初始数据...")

        try:
            # 这里可以加载一些测试数据或初始配置
            # 例如：创建默认用户、策略等

            # 示例：检查是否有活跃用户
            with mysql_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
                active_users = cursor.fetchone()[0]

                self.logger.info(f"当前活跃用户数: {active_users}")

                if active_users == 0:
                    self.logger.warning("没有活跃用户，系统将处于待机状态")
                else:
                    self.logger.info(f"系统将监控 {active_users} 个活跃用户")

        except Exception as e:
            self.logger.error(f"加载初始数据失败: {e}")

    def start(self) -> bool:
        """启动应用"""
        if self.running:
            self.logger.warning("应用已经在运行")
            return True

        self.logger.info("=" * 60)
        self.logger.info("启动高并发订单监控系统")
        self.logger.info("=" * 60)

        try:
            # 检查依赖项
            if not self._check_dependencies():
                self.logger.error("依赖项检查失败，无法启动")
                return False

            # 初始化组件
            if not self._initialize_components():
                self.logger.error("组件初始化失败，无法启动")
                return False

            # 加载初始数据
            self._load_initial_data()

            # 标记为运行状态
            self.running = True
            self.start_time = datetime.now()

            self.logger.info("=" * 60)
            self.logger.info("系统启动成功！")
            self.logger.info(f"启动时间: {self.start_time}")
            self.logger.info("=" * 60)

            return True

        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            return False

    def stop(self) -> None:
        """停止应用"""
        if not self.running:
            self.logger.warning("应用未运行")
            return

        self.logger.info("=" * 60)
        self.logger.info("正在停止订单监控系统...")
        self.logger.info("=" * 60)

        try:
            # 停止监控引擎
            if self.components['monitoring']:
                self.logger.info("停止监控引擎...")
                monitoring_engine.stop()
                self.components['monitoring'] = False

            # 停止日志管理器
            if self.components['logging']:
                self.logger.info("停止日志管理器...")
                log_manager.stop()
                self.components['logging'] = False

            # 关闭数据库连接
            if self.components['redis']:
                self.logger.info("关闭Redis连接...")
                redis_manager.close()
                self.components['redis'] = False

            if self.components['mysql']:
                self.logger.info("关闭MySQL连接...")
                mysql_manager.close()
                self.components['mysql'] = False

            # 标记为停止状态
            self.running = False

            # 计算运行时间
            if self.start_time:
                runtime = datetime.now() - self.start_time
                self.logger.info(f"系统运行时间: {runtime}")

            self.logger.info("=" * 60)
            self.logger.info("系统已安全停止")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"停止过程中发生错误: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            'running': self.running,
            'start_time': self.start_time,
            'components': self.components.copy(),
            'uptime': None
        }

        if self.start_time:
            status['uptime'] = str(datetime.now() - self.start_time)

        # 获取各组件详细状态
        try:
            if self.components['mysql']:
                status['mysql_stats'] = mysql_manager.get_pool_info()

            if self.components['redis']:
                status['redis_stats'] = redis_manager.get_connection_info()

            if self.components['logging']:
                status['logging_stats'] = log_manager.get_statistics()

            if self.components['monitoring']:
                status['monitoring_stats'] = monitoring_engine.get_statistics()

        except Exception as e:
            self.logger.error(f"获取状态信息失败: {e}")

        return status

    def run(self) -> None:
        """运行应用（阻塞模式）"""
        if not self.start():
            sys.exit(1)

        try:
            self.logger.info("系统进入运行状态，按 Ctrl+C 停止...")

            # 主循环
            while self.running:
                time.sleep(1)

                # 这里可以添加一些周期性任务
                # 例如：健康检查、状态报告等

        except KeyboardInterrupt:
            self.logger.info("接收到中断信号")

        finally:
            self.stop()

    def __repr__(self):
        return f"<OrderMonitoringApp(running={self.running})>"