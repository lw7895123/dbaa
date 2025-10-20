"""
日志管理系统
支持独立用户日志文件和自动清理功能
"""
import os
import logging
import threading
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional
import glob
from .config import config

# 全局日志器字典
_loggers: Dict[str, logging.Logger] = {}
_logger_lock = threading.Lock()


class UserLoggerManager:
    """用户日志管理器"""
    
    def __init__(self):
        self.loggers: Dict[int, logging.Logger] = {}
        self.lock = threading.Lock()
        self._setup_system_logger()
    
    def _setup_system_logger(self):
        """设置系统日志"""
        system_logger = logging.getLogger('system')
        system_logger.setLevel(getattr(logging, config.LOG_CONFIG['level']))
        
        # 避免重复添加处理器
        if not system_logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                config.LOG_CONFIG['format'],
                config.LOG_CONFIG['date_format']
            )
            console_handler.setFormatter(console_formatter)
            system_logger.addHandler(console_handler)
            
            # 文件处理器
            log_file = config.get_system_log_path()
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=config.LOG_CONFIG['max_file_size'],
                backupCount=config.LOG_CONFIG['backup_count'],
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, config.LOG_CONFIG['level']))
            file_formatter = logging.Formatter(
                config.LOG_CONFIG['format'],
                config.LOG_CONFIG['date_format']
            )
            file_handler.setFormatter(file_formatter)
            system_logger.addHandler(file_handler)
        
        self.system_logger = system_logger
    
    def get_user_logger(self, user_id: int) -> logging.Logger:
        """获取用户专用日志器"""
        with self.lock:
            if user_id not in self.loggers:
                self.loggers[user_id] = self._create_user_logger(user_id)
            return self.loggers[user_id]
    
    def _create_user_logger(self, user_id: int) -> logging.Logger:
        """创建用户专用日志器"""
        logger_name = f'user_{user_id}'
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, config.LOG_CONFIG['level']))
        
        # 避免重复添加处理器
        if not logger.handlers:
            log_file = config.get_log_file_path(user_id)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=config.LOG_CONFIG['max_file_size'],
                backupCount=config.LOG_CONFIG['backup_count'],
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, config.LOG_CONFIG['level']))
            
            formatter = logging.Formatter(
                f'%(asctime)s - USER_{user_id} - %(levelname)s - %(message)s',
                config.LOG_CONFIG['date_format']
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 防止日志传播到根日志器
            logger.propagate = False
        
        return logger
    
    def get_system_logger(self) -> logging.Logger:
        """获取系统日志器"""
        return self.system_logger
    
    def cleanup_old_logs(self):
        """清理过期日志文件"""
        try:
            log_dir = config.LOG_CONFIG['log_dir']
            if not os.path.exists(log_dir):
                return
            
            cutoff_date = datetime.now() - timedelta(days=config.LOG_CONFIG['retention_days'])
            
            # 查找所有日志文件
            log_patterns = [
                os.path.join(log_dir, 'user_*.log*'),
                os.path.join(log_dir, 'system.log*')
            ]
            
            deleted_count = 0
            for pattern in log_patterns:
                for log_file in glob.glob(pattern):
                    try:
                        # 获取文件修改时间
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                        if file_mtime < cutoff_date:
                            os.remove(log_file)
                            deleted_count += 1
                            self.system_logger.info(f"删除过期日志文件: {log_file}")
                    except Exception as e:
                        self.system_logger.error(f"删除日志文件失败 {log_file}: {e}")
            
            if deleted_count > 0:
                self.system_logger.info(f"日志清理完成，删除了 {deleted_count} 个过期文件")
        
        except Exception as e:
            self.system_logger.error(f"日志清理过程出错: {e}")
    
    def log_order_event(self, user_id: int, order_id: int, event: str, details: str = ""):
        """记录订单事件"""
        logger = self.get_user_logger(user_id)
        message = f"订单[{order_id}] {event}"
        if details:
            message += f" - {details}"
        logger.info(message)
    
    def log_order_status_change(self, user_id: int, order_id: int, old_status: str, 
                               new_status: str, filled_quantity: Optional[float] = None):
        """记录订单状态变更"""
        logger = self.get_user_logger(user_id)
        message = f"订单[{order_id}] 状态变更: {old_status} -> {new_status}"
        if filled_quantity is not None:
            message += f", 成交数量: {filled_quantity}"
        logger.info(message)
    
    def log_group_status_change(self, user_id: int, group_id: int, group_name: str, 
                               old_status: int, new_status: int):
        """记录分组状态变更"""
        logger = self.get_user_logger(user_id)
        status_map = {0: "关闭", 1: "开启"}
        old_status_text = status_map.get(old_status, str(old_status))
        new_status_text = status_map.get(new_status, str(new_status))
        message = f"分组[{group_id}:{group_name}] 状态变更: {old_status_text} -> {new_status_text}"
        logger.info(message)
    
    def log_user_status_change(self, user_id: int, username: str, old_status: int, new_status: int):
        """记录用户状态变更"""
        logger = self.get_user_logger(user_id)
        status_map = {0: "禁用", 1: "启用"}
        old_status_text = status_map.get(old_status, str(old_status))
        new_status_text = status_map.get(new_status, str(new_status))
        message = f"用户[{username}] 状态变更: {old_status_text} -> {new_status_text}"
        logger.info(message)
    
    def log_monitor_start(self, user_id: int):
        """记录监控开始"""
        logger = self.get_user_logger(user_id)
        logger.info("订单监控开始")
    
    def log_monitor_stop(self, user_id: int, reason: str = ""):
        """记录监控停止"""
        logger = self.get_user_logger(user_id)
        message = "订单监控停止"
        if reason:
            message += f" - {reason}"
        logger.info(message)
    
    def log_error(self, user_id: int, error_msg: str, exception: Optional[Exception] = None):
        """记录错误"""
        logger = self.get_user_logger(user_id)
        if exception:
            logger.error(f"{error_msg}: {str(exception)}", exc_info=True)
        else:
            logger.error(error_msg)
    
    def log_warning(self, user_id: int, warning_msg: str):
        """记录警告"""
        logger = self.get_user_logger(user_id)
        logger.warning(warning_msg)


class LogCleanupScheduler:
    """日志清理调度器"""
    
    def __init__(self, logger_manager: UserLoggerManager):
        self.logger_manager = logger_manager
        self.cleanup_timer = None
        self.is_running = False
    
    def start_cleanup_schedule(self, interval_hours: int = 24):
        """启动定时清理任务"""
        if self.is_running:
            return
        
        self.is_running = True
        self._schedule_cleanup(interval_hours)
        self.logger_manager.get_system_logger().info(f"日志清理调度器已启动，清理间隔: {interval_hours}小时")
    
    def stop_cleanup_schedule(self):
        """停止定时清理任务"""
        if self.cleanup_timer:
            self.cleanup_timer.cancel()
            self.cleanup_timer = None
        self.is_running = False
        self.logger_manager.get_system_logger().info("日志清理调度器已停止")
    
    def _schedule_cleanup(self, interval_hours: int):
        """调度下一次清理"""
        if not self.is_running:
            return
        
        # 执行清理
        self.logger_manager.cleanup_old_logs()
        
        # 调度下一次清理
        self.cleanup_timer = threading.Timer(
            interval_hours * 3600,  # 转换为秒
            self._schedule_cleanup,
            args=(interval_hours,)
        )
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()


# 全局日志管理器实例
logger_manager = UserLoggerManager()
cleanup_scheduler = LogCleanupScheduler(logger_manager)


def get_user_logger(user_id: int) -> logging.Logger:
    """获取用户日志器的便捷函数"""
    return logger_manager.get_user_logger(user_id)


def get_system_logger() -> logging.Logger:
    """获取系统日志器的便捷函数"""
    return logger_manager.get_system_logger()


def start_log_cleanup():
    """启动日志清理调度"""
    cleanup_scheduler.start_cleanup_schedule()


def stop_log_cleanup():
    """停止日志清理调度"""
    cleanup_scheduler.stop_cleanup_schedule()


# 模块级别的便捷日志函数
def log_order_event(user_id: int, order_id: int, event: str, details: str = ""):
    """记录订单事件"""
    logger_manager.log_order_event(user_id, order_id, event, details)


def log_order_status_change(user_id: int, order_id: int, old_status: str, 
                           new_status: str, filled_quantity: Optional[float] = None):
    """记录订单状态变更"""
    logger_manager.log_order_status_change(user_id, order_id, old_status, new_status, filled_quantity)


def log_group_status_change(user_id: int, group_id: int, group_name: str, 
                           old_status: int, new_status: int):
    """记录分组状态变更"""
    logger_manager.log_group_status_change(user_id, group_id, group_name, old_status, new_status)


def log_user_status_change(user_id: int, username: str, old_status: int, new_status: int):
    """记录用户状态变更"""
    logger_manager.log_user_status_change(user_id, username, old_status, new_status)


def log_system_info(message: str):
    """记录系统信息"""
    get_system_logger().info(message)


def log_monitor_start(user_id: int):
    """记录监控开始"""
    logger_manager.log_monitor_start(user_id)


def log_monitor_stop(user_id: int, reason: str = ""):
    """记录监控停止"""
    logger_manager.log_monitor_stop(user_id, reason)


def log_system_error(message: str, exception: Optional[Exception] = None):
    """记录系统错误"""
    if exception:
        get_system_logger().error(f"{message}: {str(exception)}", exc_info=True)
    else:
        get_system_logger().error(message)