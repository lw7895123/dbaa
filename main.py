"""
高并发订单监控系统 - 主启动文件
"""
import os
import sys
import signal
import time
import argparse
from typing import Optional

# 添加app目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.config import config
from app.database import db_manager
from app.redis_client import redis_manager, cache_service
from app.logger import get_system_logger, LogCleanupScheduler, logger_manager
from app.monitor_engine import MonitorEngine
from app.event_handler import event_monitor
from app.status_monitor import status_monitor, status_controller


class OrderMonitoringSystem:
    """订单监控系统主类"""
    
    def __init__(self):
        self.logger = get_system_logger()
        self.monitor_engine: Optional[MonitorEngine] = None
        self.log_cleanup_scheduler: Optional[LogCleanupScheduler] = None
        self.is_running = False
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"接收到信号 {signum}, 开始优雅关闭...")
        self.stop()
    
    def initialize(self) -> bool:
        """初始化系统"""
        try:
            self.logger.info("开始初始化订单监控系统...")
            
            # 1. 测试数据库连接
            self.logger.info("测试数据库连接...")
            if not self._test_database_connection():
                return False
            
            # 2. 测试Redis连接
            self.logger.info("测试Redis连接...")
            if not self._test_redis_connection():
                return False
            
            # 3. 初始化监控引擎
            self.logger.info("初始化监控引擎...")
            self.monitor_engine = MonitorEngine(
                worker_count=config.MONITOR_WORKER_COUNT,
                batch_size=config.MONITOR_BATCH_SIZE
            )
            
            # 4. 初始化日志清理调度器
            self.logger.info("初始化日志清理调度器...")
            self.log_cleanup_scheduler = LogCleanupScheduler(logger_manager)
            
            # 5. 强制刷新状态缓存
            self.logger.info("刷新状态缓存...")
            status_monitor.force_refresh_cache()
            
            self.logger.info("系统初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"系统初始化失败: {e}")
            return False
    
    def _test_database_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 id")
                    result = cursor.fetchone()
                    if result and result["id"] == 1:
                        self.logger.info("数据库连接测试成功")
                        return True
            return False
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def _test_redis_connection(self) -> bool:
        """测试Redis连接"""
        try:
            redis_client = redis_manager.get_client()
            redis_client.ping()
            self.logger.info("Redis连接测试成功")
            return True
        except Exception as e:
            self.logger.error(f"Redis连接测试失败: {e}")
            return False
    
    def start(self) -> bool:
        """启动系统"""
        if self.is_running:
            self.logger.warning("系统已在运行")
            return True
        
        try:
            self.logger.info("启动订单监控系统...")
            self.logger.info("系统监控开始")
            
            # 1. 启动状态监控器
            self.logger.info("启动状态监控器...")
            status_monitor.start()
            
            # 2. 启动事件监控器
            self.logger.info("启动事件监控器...")
            event_monitor.start()
            
            # 3. 启动监控引擎
            self.logger.info("启动监控引擎...")
            if not self.monitor_engine.start():
                self.logger.error("监控引擎启动失败")
                return False
            
            # 4. 启动日志清理调度器
            self.logger.info("启动日志清理调度器...")
            self.log_cleanup_scheduler.start_cleanup_schedule()
            
            self.is_running = True
            self.logger.info("订单监控系统启动成功")
            
            # 显示系统状态
            self._show_system_status()
            
            return True
            
        except Exception as e:
            self.logger.error(f"系统启动失败: {e}")
            self.stop()
            return False
    
    def stop(self):
        """停止系统"""
        if not self.is_running:
            return
        
        try:
            self.logger.info("停止订单监控系统...")
            self.logger.info("系统监控停止")
            
            # 1. 停止监控引擎
            if self.monitor_engine:
                self.logger.info("停止监控引擎...")
                self.monitor_engine.stop()
            
            # 2. 停止事件监控器
            self.logger.info("停止事件监控器...")
            event_monitor.stop()
            
            # 3. 停止状态监控器
            self.logger.info("停止状态监控器...")
            status_monitor.stop()
            
            # 4. 停止日志清理调度器
            if self.log_cleanup_scheduler:
                self.logger.info("停止日志清理调度器...")
                self.log_cleanup_scheduler.stop_cleanup_schedule()
            
            # 5. 关闭数据库连接池
            self.logger.info("关闭数据库连接池...")
            db_manager.close_all()
            
            # 6. 关闭Redis连接池
            self.logger.info("关闭Redis连接池...")
            redis_manager.close()
            
            self.is_running = False
            self.logger.info("订单监控系统已停止")
            
        except Exception as e:
            self.logger.error(f"系统停止异常: {e}")
    
    def _show_system_status(self):
        """显示系统状态"""
        try:
            # 获取监控引擎状态
            engine_status = self.monitor_engine.get_status()
            
            # 获取状态监控摘要
            status_summary = status_monitor.get_status_summary()
            
            # 获取缓存统计
            cache_stats = cache_service.get_monitor_stats()
            
            self.logger.info("=" * 60)
            self.logger.info("系统状态摘要:")
            self.logger.info(f"监控引擎: {'运行中' if engine_status['is_running'] else '已停止'}")
            self.logger.info(f"工作进程数: {engine_status['worker_count']}")
            self.logger.info(f"活跃进程数: {engine_status['active_workers']}")
            
            if status_summary:
                user_stats = status_summary.get('user_stats', {})
                group_stats = status_summary.get('group_stats', {})
                self.logger.info(f"用户状态统计: {user_stats}")
                self.logger.info(f"分组状态统计: {group_stats}")
            
            if cache_stats:
                self.logger.info(f"缓存统计: {cache_stats}")
            
            self.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.error(f"显示系统状态失败: {e}")
    
    def run(self):
        """运行系统（阻塞模式）"""
        if not self.start():
            sys.exit(1)
        
        try:
            self.logger.info("系统运行中，按 Ctrl+C 停止...")
            
            # 主循环
            while self.is_running:
                time.sleep(10)
                
                # 定期显示状态（可选）
                if hasattr(self, '_last_status_time'):
                    if time.time() - self._last_status_time > 300:  # 5分钟
                        self._show_system_status()
                        self._last_status_time = time.time()
                else:
                    self._last_status_time = time.time()
        
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号")
        
        finally:
            self.stop()


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='高并发订单监控系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 启动系统
  python main.py --test             # 测试连接
  python main.py --status           # 显示状态
  python main.py --init-cache       # 初始化缓存
        """
    )
    
    parser.add_argument(
        '--test', 
        action='store_true',
        help='测试数据库和Redis连接'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='显示系统状态'
    )
    
    parser.add_argument(
        '--init-cache',
        action='store_true',
        help='初始化状态缓存'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='指定配置文件路径'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='设置日志级别'
    )
    
    return parser


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    if args.log_level:
        import logging
        logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 创建系统实例
    system = OrderMonitoringSystem()
    
    # 处理命令行参数
    if args.test:
        # 测试连接
        print("测试系统连接...")
        if system.initialize():
            print("✓ 所有连接测试通过")
            system.stop()
            sys.exit(0)
        else:
            print("✗ 连接测试失败")
            sys.exit(1)
    
    elif args.status:
        # 显示状态
        if system.initialize():
            system._show_system_status()
            system.stop()
        sys.exit(0)
    
    elif args.init_cache:
        # 初始化缓存
        print("初始化状态缓存...")
        if system.initialize():
            status_monitor.force_refresh_cache()
            print("✓ 缓存初始化完成")
            system.stop()
            sys.exit(0)
        else:
            print("✗ 缓存初始化失败")
            sys.exit(1)
    
    else:
        # 正常启动系统
        print("启动高并发订单监控系统...")
        print(f"配置环境: {config.ENV}")
        print(f"工作进程数: {config.MONITOR_WORKER_COUNT}")
        print(f"批处理大小: {config.MONITOR_BATCH_SIZE}")
        print("-" * 50)
        
        # 初始化并运行
        if system.initialize():
            system.run()
        else:
            print("系统初始化失败")
            sys.exit(1)


if __name__ == '__main__':
    main()