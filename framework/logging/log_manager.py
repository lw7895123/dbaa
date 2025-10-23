# -*- coding: utf-8 -*-
"""
日志管理器
统一管理用户日志和日志清理功能
"""
import logging
import threading
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .user_logger import UserLoggerManager, get_user_logger
from .log_cleaner import log_cleaner
from ..config import LOG_CONFIG


class LogManager:
    """日志管理器"""
    
    def __init__(self):
        """初始化日志管理器"""
        self.user_logger_manager = UserLoggerManager()
        self.log_cleaner = log_cleaner
        
        self.running = False
        self.monitor_thread = None
        self.monitor_interval = LOG_CONFIG.get('monitor_interval', 300)  # 监控间隔（秒），默认5分钟
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_log_entries': 0,
            'total_users': 0,
            'active_users': 0,
            'errors': 0,
            'last_error': None,
            'last_monitor_time': None
        }
        
        self.logger = logging.getLogger(__name__)
        self.lock = threading.RLock()
        
        self.logger.info("日志管理器初始化完成")
    
    def start(self) -> bool:
        """
        启动日志管理器
        
        Returns:
            bool: 启动是否成功
        """
        if self.running:
            self.logger.warning("日志管理器已经在运行")
            return True
        
        try:
            # 启动日志清理器
            if not self.log_cleaner.start():
                self.logger.error("启动日志清理器失败")
                return False
            
            # 启动监控线程
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="LogMonitorThread",
                daemon=True
            )
            self.monitor_thread.start()
            
            # 更新统计信息
            with self.lock:
                self.stats['start_time'] = datetime.now()
            
            self.logger.info("日志管理器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动日志管理器失败: {e}")
            self.running = False
            return False
    
    def stop(self, timeout: float = 30.0) -> None:
        """
        停止日志管理器
        
        Args:
            timeout: 停止超时时间（秒）
        """
        if not self.running:
            self.logger.warning("日志管理器未运行")
            return
        
        self.logger.info("正在停止日志管理器...")
        
        # 设置停止标志
        self.running = False
        
        # 停止监控线程
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=timeout/2)
            if self.monitor_thread.is_alive():
                self.logger.warning("监控线程未能及时停止")
        
        # 停止日志清理器
        self.log_cleaner.stop(timeout=timeout/2)
        
        # 清理所有用户日志器
        self.user_logger_manager.cleanup_all()
        
        self.logger.info("日志管理器已停止")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        self.logger.info("日志监控循环启动")
        
        while self.running:
            try:
                # 更新统计信息
                self._update_statistics()
                
                # 检查日志器健康状态
                self._check_logger_health()
                
                # 等待下次监控，使用短间隔检查停止标志
                self._interruptible_sleep(self.monitor_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                with self.lock:
                    self.stats['errors'] += 1
                    self.stats['last_error'] = str(e)
                
                # 出错时等待较短时间再重试
                self._interruptible_sleep(60)
        
        self.logger.info("日志监控循环结束")
    
    def _interruptible_sleep(self, duration: float) -> None:
        """可中断的睡眠，每秒检查一次停止标志"""
        end_time = time.time() + duration
        while time.time() < end_time and self.running:
            time.sleep(min(1.0, end_time - time.time()))
    
    def _update_statistics(self) -> None:
        """更新统计信息"""
        try:
            user_stats = self.user_logger_manager.get_statistics()
            cleaner_stats = self.log_cleaner.get_statistics()
            
            with self.lock:
                self.stats.update({
                    'total_users': user_stats.get('total_loggers', 0),
                    'active_users': user_stats.get('active_loggers', 0),
                    'last_monitor_time': datetime.now()
                })
                
                # 累计日志条目数（这里简化处理，实际可以从各个用户日志器获取）
                # 在实际应用中，可以让每个UserLogger维护自己的计数器
            
        except Exception as e:
            self.logger.error(f"更新统计信息失败: {e}")
    
    def _check_logger_health(self) -> None:
        """检查日志器健康状态"""
        try:
            # 检查用户日志器管理器
            user_stats = self.user_logger_manager.get_statistics()
            
            # 检查是否有异常的日志器
            if user_stats.get('errors', 0) > 0:
                self.logger.warning(f"用户日志器存在错误: {user_stats.get('errors')} 个")
            
            # 检查日志清理器
            cleaner_stats = self.log_cleaner.get_statistics()
            if not cleaner_stats.get('running', False):
                self.logger.warning("日志清理器未运行，尝试重启")
                self.log_cleaner.start()
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
    
    def get_user_logger(self, user_id: int):
        """
        获取用户日志器
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserLogger: 用户日志器实例
        """
        return get_user_logger(user_id)
    
    def remove_user_logger(self, user_id: int) -> bool:
        """
        移除用户日志器
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 移除是否成功
        """
        return self.user_logger_manager.remove_logger(user_id)
    
    def force_cleanup_logs(self) -> Dict[str, Any]:
        """
        强制执行日志清理
        
        Returns:
            Dict: 清理结果
        """
        return self.log_cleaner.force_cleanup()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取完整的统计信息"""
        with self.lock:
            stats = self.stats.copy()
        
        # 添加子组件统计信息
        stats['user_logger_stats'] = self.user_logger_manager.get_statistics()
        stats['log_cleaner_stats'] = self.log_cleaner.get_statistics()
        stats['running'] = self.running
        
        return stats
    
    def get_user_log_files(self, user_id: int) -> List[str]:
        """
        获取用户的日志文件列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[str]: 日志文件路径列表
        """
        try:
            user_logger = self.user_logger_manager.get_logger(user_id)
            if user_logger:
                return user_logger.get_log_files()
            return []
        except Exception as e:
            self.logger.error(f"获取用户 {user_id} 日志文件失败: {e}")
            return []
    
    def cleanup_user_logs(self, user_id: int) -> bool:
        """
        清理指定用户的日志
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 清理是否成功
        """
        try:
            user_logger = self.user_logger_manager.get_logger(user_id)
            if user_logger:
                user_logger.cleanup()
                return True
            return False
        except Exception as e:
            self.logger.error(f"清理用户 {user_id} 日志失败: {e}")
            return False
    
    def log_system_event(self, level: str, message: str, **kwargs) -> None:
        """
        记录系统级别的事件
        
        Args:
            level: 日志级别
            message: 日志消息
            **kwargs: 额外的日志参数
        """
        try:
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            
            # 格式化消息
            if kwargs:
                formatted_message = f"{message} - {kwargs}"
            else:
                formatted_message = message
            
            log_method(formatted_message)
            
            # 更新统计
            with self.lock:
                self.stats['total_log_entries'] += 1
                
        except Exception as e:
            self.logger.error(f"记录系统事件失败: {e}")
    
    def is_running(self) -> bool:
        """检查日志管理器是否正在运行"""
        return self.running
    
    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置信息"""
        return LOG_CONFIG.copy()
    
    def __repr__(self):
        return f"<LogManager(running={self.running}, users={self.stats.get('total_users', 0)})>"


# 全局日志管理器实例
log_manager = LogManager()