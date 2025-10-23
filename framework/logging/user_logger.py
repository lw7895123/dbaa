# -*- coding: utf-8 -*-
"""
用户独立日志器
为每个用户创建独立的日志文件
"""
import os
import logging
import threading
from typing import Dict, Optional
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from ..config import LOG_CONFIG


class UserLogFormatter(logging.Formatter):
    """用户日志格式化器"""
    
    def __init__(self):
        # 日志格式：日志生成时间、文件目录、发生的行数、日志级别、日志所记录的信息
        fmt = '%(asctime)s | %(pathname)s:%(lineno)d | %(levelname)s | %(message)s'
        super().__init__(fmt, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record):
        """格式化日志记录"""
        # 确保路径使用正斜杠
        record.pathname = record.pathname.replace('\\', '/')
        return super().format(record)


class UserLogger:
    """用户独立日志器"""
    
    def __init__(self, user_id: int):
        """
        初始化用户日志器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.logger_name = f"user_{user_id}"
        
        # 创建日志目录
        self.log_dir = os.path.join(LOG_CONFIG['log_dir'], f"user_{user_id}")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 日志文件路径
        self.log_file = os.path.join(self.log_dir, f"user_{user_id}.log")
        
        # 创建logger
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(getattr(logging, LOG_CONFIG['log_level']))
        
        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handlers()
        
        # 线程锁
        self.lock = threading.Lock()
        
        self.logger.info(f"用户日志器初始化: 用户 {user_id}, 日志文件: {self.log_file}")
    
    def _setup_handlers(self) -> None:
        """设置日志处理器"""
        # 文件处理器 - 按天轮转
        file_handler = TimedRotatingFileHandler(
            filename=self.log_file,
            when='midnight',
            interval=1,
            backupCount=LOG_CONFIG['backup_count'],  # 保留7天
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, LOG_CONFIG['log_level']))
        file_handler.setFormatter(UserLogFormatter())
        
        # 设置轮转文件名后缀
        file_handler.suffix = "%Y-%m-%d"
        
        self.logger.addHandler(file_handler)
        
        # 如果启用控制台输出
        if LOG_CONFIG.get('console_output', False):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, LOG_CONFIG['log_level']))
            console_handler.setFormatter(UserLogFormatter())
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录DEBUG级别日志"""
        with self.lock:
            self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """记录INFO级别日志"""
        with self.lock:
            self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录WARNING级别日志"""
        with self.lock:
            self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """记录ERROR级别日志"""
        with self.lock:
            self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """记录CRITICAL级别日志"""
        with self.lock:
            self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """记录异常日志"""
        with self.lock:
            self.logger.exception(message, **kwargs)
    
    def log_order_event(self, event_type: str, order_no: str, details: str) -> None:
        """记录订单事件"""
        message = f"[订单事件] {event_type} | 订单号: {order_no} | {details}"
        self.info(message)
    
    def log_strategy_event(self, event_type: str, strategy_name: str, details: str) -> None:
        """记录策略事件"""
        message = f"[策略事件] {event_type} | 策略: {strategy_name} | {details}"
        self.info(message)
    
    def log_trade_event(self, symbol: str, side: str, quantity: float, price: float, details: str = "") -> None:
        """记录交易事件"""
        message = f"[交易事件] {symbol} | {side} | 数量: {quantity} | 价格: {price}"
        if details:
            message += f" | {details}"
        self.info(message)
    
    def log_error_event(self, error_type: str, error_message: str, details: str = "") -> None:
        """记录错误事件"""
        message = f"[错误事件] {error_type} | {error_message}"
        if details:
            message += f" | {details}"
        self.error(message)
    
    def log_performance_metrics(self, metrics: Dict) -> None:
        """记录性能指标"""
        message = f"[性能指标] {metrics}"
        self.info(message)
    
    def get_log_file_path(self) -> str:
        """获取日志文件路径"""
        return self.log_file
    
    def get_log_dir(self) -> str:
        """获取日志目录"""
        return self.log_dir
    
    def cleanup(self) -> None:
        """清理日志器"""
        try:
            # 移除所有处理器
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            
            # 从日志管理器中移除
            logging.getLogger(self.logger_name).handlers.clear()
            
        except Exception as e:
            print(f"清理用户日志器失败: 用户 {self.user_id}, 错误: {e}")


class UserLoggerManager:
    """用户日志器管理器"""
    
    def __init__(self):
        """初始化用户日志器管理器"""
        self.user_loggers = {}  # {user_id: UserLogger}
        self.lock = threading.RLock()
    
    def get_user_logger(self, user_id: int) -> UserLogger:
        """
        获取用户日志器
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserLogger: 用户日志器实例
        """
        with self.lock:
            if user_id not in self.user_loggers:
                self.user_loggers[user_id] = UserLogger(user_id)
            return self.user_loggers[user_id]
    
    def remove_user_logger(self, user_id: int) -> None:
        """
        移除用户日志器
        
        Args:
            user_id: 用户ID
        """
        with self.lock:
            if user_id in self.user_loggers:
                logger = self.user_loggers[user_id]
                logger.cleanup()
                del self.user_loggers[user_id]
    
    def cleanup_all(self) -> None:
        """清理所有用户日志器"""
        with self.lock:
            for user_id in list(self.user_loggers.keys()):
                self.remove_user_logger(user_id)
    
    def get_active_user_count(self) -> int:
        """获取活跃用户日志器数量"""
        with self.lock:
            return len(self.user_loggers)
    
    def get_active_users(self) -> list:
        """获取活跃用户列表"""
        with self.lock:
            return list(self.user_loggers.keys())
    
    def get_statistics(self) -> Dict:
        """获取用户日志器统计信息"""
        with self.lock:
            return {
                'active_user_count': len(self.user_loggers),
                'active_users': list(self.user_loggers.keys()),
                'total_loggers': len(self.user_loggers)
            }


# 全局用户日志器管理器
_user_logger_manager = UserLoggerManager()


def get_user_logger(user_id: int) -> UserLogger:
    """
    获取用户日志器的便捷函数
    
    Args:
        user_id: 用户ID
        
    Returns:
        UserLogger: 用户日志器实例
    """
    return _user_logger_manager.get_user_logger(user_id)


def remove_user_logger(user_id: int) -> None:
    """
    移除用户日志器的便捷函数
    
    Args:
        user_id: 用户ID
    """
    _user_logger_manager.remove_user_logger(user_id)


def cleanup_all_user_loggers() -> None:
    """清理所有用户日志器的便捷函数"""
    _user_logger_manager.cleanup_all()