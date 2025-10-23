# -*- coding: utf-8 -*-
"""
高并发监控引擎
负责管理所有用户的监控器，实现高并发订单监控
"""
import threading
import time
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..database import mysql_manager, redis_manager
from ..config import MONITOR_CONFIG, SYSTEM_STATUS
from .user_monitor import UserMonitor
from .event_handler import event_handler, EventType


class MonitoringEngine:
    """高并发监控引擎"""
    
    def __init__(self):
        """初始化监控引擎"""
        self.user_monitors = {}  # {user_id: UserMonitor}
        self.running = False
        
        # 配置参数
        self.max_concurrent_users = MONITOR_CONFIG.get('max_workers', 100)
        self.user_scan_interval = MONITOR_CONFIG.get('check_interval', 0.1)
        self.health_check_interval = SYSTEM_STATUS.get('health_check_interval', 10)
        
        # 线程管理
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent_users,
            thread_name_prefix="MonitoringEngine"
        )
        self.scan_thread = None
        self.health_check_thread = None
        
        # 控制锁
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_users_monitored': 0,
            'active_users': 0,
            'total_scans': 0,
            'failed_starts': 0,
            'failed_stops': 0,
            'last_scan_time': None,
            'last_health_check': None
        }
        
        self.logger = logging.getLogger(__name__)
        
        # 注册事件处理器
        self._register_event_handlers()
        
        self.logger.info(f"监控引擎初始化: 最大并发用户 {self.max_concurrent_users}")
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        # 注册系统错误事件处理器
        event_handler.register_handler(EventType.SYSTEM_ERROR, self._handle_system_error)
        
        # 注册用户激活/停用事件处理器
        event_handler.register_handler(EventType.USER_ACTIVATE, self._handle_user_activate)
        event_handler.register_handler(EventType.USER_DEACTIVATE, self._handle_user_deactivate)
    
    def _handle_system_error(self, event) -> None:
        """处理系统错误事件"""
        self.logger.error(f"系统错误事件: 用户 {event.user_id}, 错误: {event.data.get('error')}")
        
        # 如果是严重错误，可能需要重启用户监控
        error_type = event.data.get('error_type')
        if error_type in ['database_connection', 'redis_connection']:
            self.logger.warning(f"检测到连接错误，尝试重启用户监控: 用户 {event.user_id}")
            self._restart_user_monitor(event.user_id)
    
    def _handle_user_activate(self, event) -> None:
        """处理用户激活事件"""
        self.logger.info(f"用户激活: {event.user_id}")
        with self.lock:
            self.stats['active_users'] = len([m for m in self.user_monitors.values() if m.is_running()])
    
    def _handle_user_deactivate(self, event) -> None:
        """处理用户停用事件"""
        self.logger.info(f"用户停用: {event.user_id}")
        with self.lock:
            self.stats['active_users'] = len([m for m in self.user_monitors.values() if m.is_running()])
    
    def _scan_active_users(self) -> List[int]:
        """扫描需要监控的活跃用户"""
        try:
            # 从Redis获取活跃用户列表
            active_users = redis_manager.get_active_users()
            
            if not active_users:
                # 如果Redis中没有，从数据库查询有活跃策略的用户
                users_with_strategies = mysql_manager.get_users_with_active_strategies()
                active_users = [user['id'] for user in users_with_strategies]
                
                # 更新Redis缓存
                for user_id in active_users:
                    redis_manager.add_active_user(user_id)
            
            self.logger.debug(f"扫描到活跃用户: {len(active_users)} 个")
            return active_users
            
        except Exception as e:
            self.logger.error(f"扫描活跃用户失败: {e}")
            return []
    
    def _start_user_monitor(self, user_id: int) -> bool:
        """
        启动用户监控器
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 启动是否成功
        """
        try:
            with self.lock:
                # 检查是否已经在监控
                if user_id in self.user_monitors:
                    monitor = self.user_monitors[user_id]
                    if monitor.is_running():
                        self.logger.debug(f"用户监控已在运行: {user_id}")
                        return True
                    else:
                        # 清理旧的监控器
                        monitor.cleanup()
                        del self.user_monitors[user_id]
                
                # 创建新的监控器
                monitor = UserMonitor(user_id)
                
                # 启动监控器
                if monitor.start():
                    self.user_monitors[user_id] = monitor
                    self.stats['total_users_monitored'] += 1
                    self.logger.info(f"用户监控启动成功: {user_id}")
                    return True
                else:
                    self.logger.warning(f"用户监控启动失败: {user_id}")
                    monitor.cleanup()
                    self.stats['failed_starts'] += 1
                    return False
                    
        except Exception as e:
            self.logger.error(f"启动用户监控异常: {user_id}, 错误: {e}")
            self.stats['failed_starts'] += 1
            return False
    
    def _stop_user_monitor(self, user_id: int) -> bool:
        """
        停止用户监控器
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 停止是否成功
        """
        try:
            with self.lock:
                monitor = self.user_monitors.get(user_id)
                if not monitor:
                    self.logger.debug(f"用户监控器不存在: {user_id}")
                    return True
                
                # 停止监控器
                monitor.stop()
                monitor.cleanup()
                
                # 从字典中移除
                del self.user_monitors[user_id]
                
                self.logger.info(f"用户监控停止成功: {user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"停止用户监控异常: {user_id}, 错误: {e}")
            self.stats['failed_stops'] += 1
            return False
    
    def _restart_user_monitor(self, user_id: int) -> bool:
        """
        重启用户监控器
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 重启是否成功
        """
        self.logger.info(f"重启用户监控: {user_id}")
        
        # 先停止
        self._stop_user_monitor(user_id)
        
        # 短暂等待
        time.sleep(1.0)
        
        # 再启动
        return self._start_user_monitor(user_id)
    
    def _user_scan_loop(self) -> None:
        """用户扫描循环"""
        self.logger.info("用户扫描循环启动")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 扫描活跃用户
                active_users = set(self._scan_active_users())
                current_users = set(self.user_monitors.keys())
                
                # 需要启动的用户
                users_to_start = active_users - current_users
                
                # 需要停止的用户
                users_to_stop = current_users - active_users
                
                # 并发启动新用户监控
                if users_to_start:
                    self.logger.info(f"启动新用户监控: {len(users_to_start)} 个用户")
                    
                    futures = []
                    for user_id in users_to_start:
                        future = self.executor.submit(self._start_user_monitor, user_id)
                        futures.append((user_id, future))
                    
                    # 等待启动完成
                    for user_id, future in futures:
                        try:
                            future.result(timeout=30)  # 30秒超时
                        except Exception as e:
                            self.logger.error(f"启动用户监控超时或失败: {user_id}, 错误: {e}")
                
                # 停止不需要的用户监控
                if users_to_stop:
                    self.logger.info(f"停止用户监控: {len(users_to_stop)} 个用户")
                    
                    for user_id in users_to_stop:
                        self._stop_user_monitor(user_id)
                
                # 更新统计信息
                with self.lock:
                    self.stats['total_scans'] += 1
                    self.stats['last_scan_time'] = datetime.now()
                    self.stats['active_users'] = len([m for m in self.user_monitors.values() if m.is_running()])
                
                # 计算休眠时间
                elapsed = time.time() - start_time
                sleep_time = max(0, self.user_scan_interval - elapsed)
                
                if sleep_time > 0:
                    self._interruptible_sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"用户扫描循环异常: {e}")
                self._interruptible_sleep(5.0)  # 出错时休息5秒
        
        self.logger.info("用户扫描循环结束")
    
    def _health_check_loop(self) -> None:
        """健康检查循环"""
        self.logger.info("健康检查循环启动")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 检查所有用户监控器的健康状态
                unhealthy_users = []
                
                with self.lock:
                    for user_id, monitor in list(self.user_monitors.items()):
                        if not monitor.is_running():
                            unhealthy_users.append(user_id)
                            self.logger.warning(f"检测到不健康的用户监控: {user_id}")
                
                # 重启不健康的监控器
                for user_id in unhealthy_users:
                    self.logger.info(f"重启不健康的用户监控: {user_id}")
                    self._restart_user_monitor(user_id)
                
                # 检查数据库连接健康状态
                if not mysql_manager.health_check():
                    self.logger.error("MySQL连接不健康")
                    # 发送系统错误事件
                    event_handler.emit_event(
                        EventType.SYSTEM_ERROR,
                        datetime.now(),
                        0,  # 系统级错误
                        {'error_type': 'database_connection', 'error': 'MySQL health check failed'}
                    )
                
                if not redis_manager.health_check():
                    self.logger.error("Redis连接不健康")
                    # 发送系统错误事件
                    event_handler.emit_event(
                        EventType.SYSTEM_ERROR,
                        datetime.now(),
                        0,  # 系统级错误
                        {'error_type': 'redis_connection', 'error': 'Redis health check failed'}
                    )
                
                # 更新统计信息
                with self.lock:
                    self.stats['last_health_check'] = datetime.now()
                
                # 计算休眠时间
                elapsed = time.time() - start_time
                sleep_time = max(0, self.health_check_interval - elapsed)
                
                if sleep_time > 0:
                    self._interruptible_sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"健康检查循环异常: {e}")
                self._interruptible_sleep(10.0)  # 出错时休息10秒
        
        self.logger.info("健康检查循环结束")
    
    def _interruptible_sleep(self, duration: float) -> None:
        """可中断的睡眠，每秒检查一次停止标志"""
        end_time = time.time() + duration
        while time.time() < end_time and self.running:
            time.sleep(min(1.0, end_time - time.time()))
    
    def start(self) -> bool:
        """
        启动监控引擎
        
        Returns:
            bool: 启动是否成功
        """
        if self.running:
            self.logger.warning("监控引擎已经在运行")
            return True
        
        try:
            self.logger.info("启动监控引擎...")
            
            # 启动事件处理器
            event_handler.start()
            
            # 设置运行标志
            self.running = True
            self.stats['start_time'] = datetime.now()
            
            # 启动用户扫描线程
            self.scan_thread = threading.Thread(
                target=self._user_scan_loop,
                name="UserScanThread",
                daemon=True
            )
            self.scan_thread.start()
            
            # 启动健康检查线程
            self.health_check_thread = threading.Thread(
                target=self._health_check_loop,
                name="HealthCheckThread",
                daemon=True
            )
            self.health_check_thread.start()
            
            self.logger.info("监控引擎启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动监控引擎失败: {e}")
            self.running = False
            return False
    
    def stop(self, timeout: float = 30.0) -> None:
        """
        停止监控引擎
        
        Args:
            timeout: 停止超时时间（秒）
        """
        if not self.running:
            self.logger.warning("监控引擎未运行")
            return
        
        self.logger.info("正在停止监控引擎...")
        
        # 设置停止标志
        self.running = False
        
        # 停止所有用户监控器
        with self.lock:
            user_ids = list(self.user_monitors.keys())
        
        self.logger.info(f"停止 {len(user_ids)} 个用户监控器")
        
        # 并发停止所有用户监控器
        futures = []
        for user_id in user_ids:
            future = self.executor.submit(self._stop_user_monitor, user_id)
            futures.append(future)
        
        # 等待所有监控器停止
        for future in as_completed(futures, timeout=timeout):
            try:
                future.result()
            except Exception as e:
                self.logger.error(f"停止用户监控器失败: {e}")
        
        # 等待扫描线程结束
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=5.0)
            if self.scan_thread.is_alive():
                self.logger.warning("用户扫描线程未能及时停止")
        
        # 等待健康检查线程结束
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5.0)
            if self.health_check_thread.is_alive():
                self.logger.warning("健康检查线程未能及时停止")
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 停止事件处理器
        event_handler.stop()
        
        self.logger.info("监控引擎已停止")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.stats.copy()
            
            # 添加实时统计
            stats.update({
                'running': self.running,
                'total_user_monitors': len(self.user_monitors),
                'active_user_monitors': len([m for m in self.user_monitors.values() if m.is_running()]),
                'event_handler_stats': event_handler.get_statistics(),
                'user_monitor_details': {
                    user_id: monitor.get_statistics() 
                    for user_id, monitor in self.user_monitors.items()
                }
            })
            
            if stats['start_time']:
                stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
            
            return stats
    
    def get_user_monitor(self, user_id: int) -> Optional[UserMonitor]:
        """获取指定用户的监控器"""
        with self.lock:
            return self.user_monitors.get(user_id)
    
    def force_user_scan(self) -> None:
        """强制执行用户扫描"""
        self.logger.info("强制执行用户扫描")
        try:
            # 这里可以触发一次立即扫描
            # 实际实现中可以使用事件或信号来触发
            pass
        except Exception as e:
            self.logger.error(f"强制用户扫描失败: {e}")
    
    def restart_user_monitor(self, user_id: int) -> bool:
        """
        重启指定用户的监控器
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 重启是否成功
        """
        return self._restart_user_monitor(user_id)
    
    def is_running(self) -> bool:
        """检查监控引擎是否正在运行"""
        return self.running
    
    def __repr__(self):
        return f"<MonitoringEngine(running={self.running}, users={len(self.user_monitors)})>"


# 全局监控引擎实例
monitoring_engine = MonitoringEngine()