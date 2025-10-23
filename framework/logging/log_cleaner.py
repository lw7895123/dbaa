# -*- coding: utf-8 -*-
"""
日志清理器
负责自动清理超过7天的日志文件
"""
import os
import threading
import time
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from ..config import LOG_CONFIG


class LogCleaner:
    """日志清理器"""
    
    def __init__(self):
        """初始化日志清理器"""
        self.log_dir = LOG_CONFIG['log_dir']
        self.retention_days = LOG_CONFIG['retention_days']  # 保留天数
        self.cleanup_interval = LOG_CONFIG.get('cleanup_interval', 3600)  # 清理间隔（秒），默认1小时
        
        self.running = False
        self.cleanup_thread = None
        
        # 统计信息
        self.stats = {
            'total_cleanups': 0,
            'total_files_deleted': 0,
            'total_bytes_freed': 0,
            'last_cleanup_time': None,
            'last_cleanup_duration': 0,
            'errors': 0,
            'last_error': None
        }
        
        self.logger = logging.getLogger(__name__)
        self.lock = threading.RLock()
        
        self.logger.info(f"日志清理器初始化: 日志目录 {self.log_dir}, 保留天数 {self.retention_days}")
    
    def _get_expired_files(self) -> List[Dict[str, Any]]:
        """
        获取过期的日志文件
        
        Returns:
            List[Dict]: 过期文件信息列表
        """
        expired_files = []
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        try:
            if not os.path.exists(self.log_dir):
                self.logger.warning(f"日志目录不存在: {self.log_dir}")
                return expired_files
            
            # 遍历所有用户日志目录
            for user_dir in os.listdir(self.log_dir):
                user_dir_path = os.path.join(self.log_dir, user_dir)
                
                if not os.path.isdir(user_dir_path):
                    continue
                
                if not user_dir.startswith('user_'):
                    continue
                
                # 遍历用户目录中的日志文件
                for filename in os.listdir(user_dir_path):
                    file_path = os.path.join(user_dir_path, filename)
                    
                    if not os.path.isfile(file_path):
                        continue
                    
                    # 检查文件扩展名
                    if not filename.endswith('.log'):
                        continue
                    
                    try:
                        # 获取文件修改时间
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        # 检查是否过期
                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            expired_files.append({
                                'path': file_path,
                                'user_dir': user_dir,
                                'filename': filename,
                                'mtime': file_mtime,
                                'size': file_size
                            })
                    
                    except (OSError, ValueError) as e:
                        self.logger.error(f"获取文件信息失败: {file_path}, 错误: {e}")
                        continue
            
            self.logger.debug(f"找到 {len(expired_files)} 个过期日志文件")
            return expired_files
            
        except Exception as e:
            self.logger.error(f"扫描过期文件失败: {e}")
            return []
    
    def _delete_file(self, file_info: Dict[str, Any]) -> bool:
        """
        删除单个文件
        
        Args:
            file_info: 文件信息
            
        Returns:
            bool: 删除是否成功
        """
        try:
            file_path = file_info['path']
            
            # 检查文件是否仍然存在
            if not os.path.exists(file_path):
                self.logger.debug(f"文件已不存在: {file_path}")
                return True
            
            # 删除文件
            os.remove(file_path)
            
            self.logger.info(f"删除过期日志文件: {file_path} (大小: {file_info['size']} 字节)")
            return True
            
        except Exception as e:
            self.logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
            return False
    
    def _cleanup_empty_directories(self) -> int:
        """
        清理空的用户日志目录
        
        Returns:
            int: 删除的目录数量
        """
        deleted_dirs = 0
        
        try:
            if not os.path.exists(self.log_dir):
                return 0
            
            for user_dir in os.listdir(self.log_dir):
                user_dir_path = os.path.join(self.log_dir, user_dir)
                
                if not os.path.isdir(user_dir_path):
                    continue
                
                if not user_dir.startswith('user_'):
                    continue
                
                # 检查目录是否为空
                try:
                    if not os.listdir(user_dir_path):
                        os.rmdir(user_dir_path)
                        self.logger.info(f"删除空的用户日志目录: {user_dir_path}")
                        deleted_dirs += 1
                except OSError as e:
                    self.logger.error(f"删除空目录失败: {user_dir_path}, 错误: {e}")
            
            return deleted_dirs
            
        except Exception as e:
            self.logger.error(f"清理空目录失败: {e}")
            return 0
    
    def cleanup_once(self) -> Dict[str, Any]:
        """
        执行一次清理操作
        
        Returns:
            Dict: 清理结果统计
        """
        start_time = time.time()
        cleanup_stats = {
            'files_deleted': 0,
            'bytes_freed': 0,
            'dirs_deleted': 0,
            'errors': 0,
            'duration': 0
        }
        
        try:
            self.logger.info("开始执行日志清理")
            
            # 获取过期文件
            expired_files = self._get_expired_files()
            
            if not expired_files:
                self.logger.info("没有找到过期的日志文件")
                cleanup_stats['duration'] = time.time() - start_time
                return cleanup_stats
            
            self.logger.info(f"找到 {len(expired_files)} 个过期日志文件，开始删除")
            
            # 删除过期文件
            for file_info in expired_files:
                if self._delete_file(file_info):
                    cleanup_stats['files_deleted'] += 1
                    cleanup_stats['bytes_freed'] += file_info['size']
                else:
                    cleanup_stats['errors'] += 1
            
            # 清理空目录
            cleanup_stats['dirs_deleted'] = self._cleanup_empty_directories()
            
            # 更新统计信息
            with self.lock:
                self.stats['total_cleanups'] += 1
                self.stats['total_files_deleted'] += cleanup_stats['files_deleted']
                self.stats['total_bytes_freed'] += cleanup_stats['bytes_freed']
                self.stats['last_cleanup_time'] = datetime.now()
                self.stats['errors'] += cleanup_stats['errors']
            
            cleanup_stats['duration'] = time.time() - start_time
            
            self.logger.info(
                f"日志清理完成: 删除文件 {cleanup_stats['files_deleted']} 个, "
                f"释放空间 {cleanup_stats['bytes_freed']} 字节, "
                f"删除目录 {cleanup_stats['dirs_deleted']} 个, "
                f"耗时 {cleanup_stats['duration']:.2f} 秒"
            )
            
            return cleanup_stats
            
        except Exception as e:
            self.logger.error(f"日志清理失败: {e}")
            cleanup_stats['errors'] += 1
            cleanup_stats['duration'] = time.time() - start_time
            
            with self.lock:
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
            
            return cleanup_stats
    
    def _cleanup_loop(self) -> None:
        """清理循环"""
        self.logger.info("日志清理循环启动")
        
        while self.running:
            try:
                # 执行清理
                cleanup_stats = self.cleanup_once()
                
                # 更新统计信息
                with self.lock:
                    self.stats['last_cleanup_duration'] = cleanup_stats['duration']
                
                # 等待下次清理，使用短间隔检查停止标志
                self._interruptible_sleep(self.cleanup_interval)
                
            except Exception as e:
                self.logger.error(f"清理循环异常: {e}")
                with self.lock:
                    self.stats['errors'] += 1
                    self.stats['last_error'] = str(e)
                
                # 出错时等待较短时间再重试
                self._interruptible_sleep(60)
        
        self.logger.info("日志清理循环结束")
    
    def _interruptible_sleep(self, duration: float) -> None:
        """可中断的睡眠，每秒检查一次停止标志"""
        end_time = time.time() + duration
        while time.time() < end_time and self.running:
            time.sleep(min(1.0, end_time - time.time()))
    
    def start(self) -> bool:
        """
        启动日志清理器
        
        Returns:
            bool: 启动是否成功
        """
        if self.running:
            self.logger.warning("日志清理器已经在运行")
            return True
        
        try:
            # 确保日志目录存在
            os.makedirs(self.log_dir, exist_ok=True)
            
            # 启动清理线程
            self.running = True
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name="LogCleanupThread",
                daemon=True
            )
            self.cleanup_thread.start()
            
            self.logger.info("日志清理器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动日志清理器失败: {e}")
            self.running = False
            return False
    
    def stop(self, timeout: float = 10.0) -> None:
        """
        停止日志清理器
        
        Args:
            timeout: 停止超时时间（秒）
        """
        if not self.running:
            self.logger.warning("日志清理器未运行")
            return
        
        self.logger.info("正在停止日志清理器...")
        
        # 设置停止标志
        self.running = False
        
        # 等待清理线程结束
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=timeout)
            if self.cleanup_thread.is_alive():
                self.logger.warning("清理线程未能及时停止")
        
        self.logger.info("日志清理器已停止")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.stats.copy()
            stats.update({
                'running': self.running,
                'log_dir': self.log_dir,
                'retention_days': self.retention_days,
                'cleanup_interval': self.cleanup_interval
            })
            
            # 添加磁盘使用情况
            try:
                if os.path.exists(self.log_dir):
                    total_size = 0
                    file_count = 0
                    
                    for root, dirs, files in os.walk(self.log_dir):
                        for file in files:
                            if file.endswith('.log'):
                                file_path = os.path.join(root, file)
                                try:
                                    total_size += os.path.getsize(file_path)
                                    file_count += 1
                                except OSError:
                                    pass
                    
                    stats['current_log_files'] = file_count
                    stats['current_log_size_bytes'] = total_size
                    stats['current_log_size_mb'] = round(total_size / (1024 * 1024), 2)
                
            except Exception as e:
                self.logger.error(f"获取磁盘使用情况失败: {e}")
            
            return stats
    
    def force_cleanup(self) -> Dict[str, Any]:
        """
        强制执行一次清理
        
        Returns:
            Dict: 清理结果
        """
        self.logger.info("强制执行日志清理")
        return self.cleanup_once()
    
    def is_running(self) -> bool:
        """检查清理器是否正在运行"""
        return self.running
    
    def __repr__(self):
        return f"<LogCleaner(running={self.running}, retention_days={self.retention_days})>"


# 全局日志清理器实例
log_cleaner = LogCleaner()