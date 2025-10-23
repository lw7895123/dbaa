# -*- coding: utf-8 -*-
"""
用户监控器
负责监控单个用户的策略和订单
"""
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from ..models import User, UserStrategy, Order
from ..database import mysql_manager, redis_manager
from ..strategies import StrategyManager
from ..utils import UserOrderManager
from ..logging import get_user_logger
from .event_handler import event_handler, EventType


class UserMonitor:
    """用户监控器"""
    
    def __init__(self, user_id: int):
        """
        初始化用户监控器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.user = None
        self.running = False
        self.last_check_time = datetime.now()
        
        # 组件管理器
        self.strategy_manager = StrategyManager(user_id)
        self.order_manager = UserOrderManager(user_id)
        
        # 监控配置
        self.check_interval = 1.0  # 检查间隔（秒）
        self.strategy_check_interval = 5.0  # 策略检查间隔（秒）
        self.last_strategy_check = datetime.now()
        
        # 线程管理
        self.monitor_thread = None
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_checks': 0,
            'strategy_updates': 0,
            'order_updates': 0,
            'errors': 0,
            'last_error': None
        }
        
        self.logger = get_user_logger(user_id)
        
        # 注册订单更新回调
        self.order_manager.add_order_update_callback(self._on_order_update)
        
        self.logger.info(f"用户监控器初始化: 用户 {user_id}")
    
    def _load_user_info(self) -> bool:
        """加载用户信息"""
        try:
            # 先从Redis缓存获取
            user_data = redis_manager.get_cached_user(self.user_id)
            
            if not user_data:
                # 从MySQL获取
                user_data = mysql_manager.get_user_by_id(self.user_id)
                if user_data:
                    # 缓存到Redis
                    redis_manager.cache_user(self.user_id, user_data)
            
            if user_data:
                self.user = User.from_dict(user_data)
                self.logger.debug(f"加载用户信息: {self.user.username}")
                return True
            else:
                self.logger.error(f"用户不存在: {self.user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"加载用户信息失败: {e}")
            return False
    
    def _check_user_strategies(self) -> bool:
        """检查用户策略状态"""
        try:
            # 从数据库获取最新的策略状态
            strategies_data = mysql_manager.get_user_strategies(self.user_id)
            
            if not strategies_data:
                self.logger.info(f"用户 {self.user_id} 没有活跃策略，停止监控")
                return False
            
            # 检查策略变化
            current_strategy_ids = set()
            for strategy_data in strategies_data:
                strategy = UserStrategy.from_dict(strategy_data)
                current_strategy_ids.add(strategy.id)
                
                # 检查策略是否需要启动或停止
                if strategy.is_active():
                    if not self.strategy_manager.is_strategy_running(strategy.id):
                        # 启动策略
                        success = self.strategy_manager.start_strategy(strategy)
                        if success:
                            self.stats['strategy_updates'] += 1
                            self.logger.info(f"启动策略: {strategy.name} (ID: {strategy.id})")
                            
                            # 发送策略启动事件
                            event_handler.emit_strategy_event(
                                EventType.STRATEGY_START,
                                self.user_id,
                                strategy.id,
                                {'strategy_name': strategy.name, 'strategy_type': strategy.strategy_type}
                            )
                else:
                    if self.strategy_manager.is_strategy_running(strategy.id):
                        # 停止策略
                        success = self.strategy_manager.stop_strategy(strategy.id)
                        if success:
                            self.stats['strategy_updates'] += 1
                            self.logger.info(f"停止策略: {strategy.name} (ID: {strategy.id})")
                            
                            # 发送策略停止事件
                            event_handler.emit_strategy_event(
                                EventType.STRATEGY_STOP,
                                self.user_id,
                                strategy.id,
                                {'strategy_name': strategy.name, 'reason': 'status_changed'}
                            )
            
            # 移除不再存在的策略
            running_strategy_ids = set(self.strategy_manager.get_running_strategy_ids())
            for strategy_id in running_strategy_ids - current_strategy_ids:
                self.strategy_manager.stop_strategy(strategy_id)
                self.logger.info(f"移除策略: ID {strategy_id}")
            
            return len(current_strategy_ids) > 0
            
        except Exception as e:
            self.logger.error(f"检查用户策略失败: {e}")
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            return True  # 出错时继续监控
    
    def _check_user_orders(self) -> None:
        """检查用户订单更新"""
        try:
            # 重新加载订单（如果有更新）
            self.order_manager.load_orders()
            
            # 获取活跃订单
            active_orders = self.order_manager.get_active_orders()
            
            # 将订单更新传递给策略管理器
            for order in active_orders:
                self.strategy_manager.handle_order_update(order)
            
            self.stats['order_updates'] += len(active_orders)
            
        except Exception as e:
            self.logger.error(f"检查用户订单失败: {e}")
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
    
    def _on_order_update(self, order: Order) -> None:
        """订单更新回调"""
        try:
            # 发送订单更新事件
            event_handler.emit_order_event(
                EventType.ORDER_UPDATE,
                self.user_id,
                order.id,
                order.strategy_id,
                {
                    'order_no': order.order_no,
                    'symbol': order.symbol,
                    'status': order.status,
                    'filled_quantity': float(order.filled_quantity),
                    'remaining_quantity': float(order.get_remaining_quantity())
                }
            )
            
            # 通知策略管理器
            self.strategy_manager.handle_order_update(order)
            
        except Exception as e:
            self.logger.error(f"处理订单更新回调失败: {e}")
    
    def _monitor_loop(self) -> None:
        """监控主循环"""
        self.logger.info(f"用户监控循环启动: 用户 {self.user_id}")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 检查策略状态（定期检查）
                now = datetime.now()
                if (now - self.last_strategy_check).total_seconds() >= self.strategy_check_interval:
                    has_active_strategies = self._check_user_strategies()
                    self.last_strategy_check = now
                    
                    # 如果没有活跃策略，停止监控
                    if not has_active_strategies:
                        self.logger.info(f"用户 {self.user_id} 没有活跃策略，停止监控")
                        break
                
                # 检查订单更新
                self._check_user_orders()
                
                # 更新统计信息
                self.stats['total_checks'] += 1
                self.last_check_time = now
                
                # 计算休眠时间
                elapsed = time.time() - start_time
                sleep_time = max(0, self.check_interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                time.sleep(1.0)  # 出错时短暂休息
        
        self.logger.info(f"用户监控循环结束: 用户 {self.user_id}")
    
    def start(self) -> bool:
        """
        启动用户监控
        
        Returns:
            bool: 启动是否成功
        """
        if self.running:
            self.logger.warning("用户监控已经在运行")
            return True
        
        try:
            # 加载用户信息
            if not self._load_user_info():
                return False
            
            # 检查用户是否活跃
            if not self.user.is_active():
                self.logger.warning(f"用户 {self.user_id} 不是活跃状态")
                return False
            
            # 加载订单
            if not self.order_manager.load_orders():
                self.logger.error("加载用户订单失败")
                return False
            
            # 检查是否有活跃策略
            if not self._check_user_strategies():
                self.logger.info(f"用户 {self.user_id} 没有活跃策略")
                return False
            
            # 启动监控线程
            self.running = True
            self.stats['start_time'] = datetime.now()
            
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name=f"UserMonitor-{self.user_id}",
                daemon=True
            )
            self.monitor_thread.start()
            
            # 添加到活跃用户列表
            redis_manager.add_active_user(self.user_id)
            
            # 发送用户激活事件
            from .event_handler import BaseEvent
            activate_event = BaseEvent(
                event_type=EventType.USER_ACTIVATE,
                timestamp=datetime.now(),
                user_id=self.user_id,
                data={'username': self.user.username}
            )
            event_handler.emit_event(activate_event)
            
            self.logger.info(f"用户监控启动成功: 用户 {self.user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动用户监控失败: {e}")
            self.running = False
            return False
    
    def stop(self, timeout: float = 10.0) -> None:
        """
        停止用户监控
        
        Args:
            timeout: 停止超时时间（秒）
        """
        if not self.running:
            self.logger.warning("用户监控未运行")
            return
        
        self.logger.info(f"正在停止用户监控: 用户 {self.user_id}")
        
        # 设置停止标志
        self.running = False
        
        # 停止策略管理器
        self.strategy_manager.stop_all_strategies()
        
        # 等待监控线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=timeout)
            if self.monitor_thread.is_alive():
                self.logger.warning(f"监控线程未能及时停止: 用户 {self.user_id}")
        
        # 从活跃用户列表移除
        redis_manager.remove_active_user(self.user_id)
        
        # 发送用户停用事件
        from .event_handler import BaseEvent
        deactivate_event = BaseEvent(
            event_type=EventType.USER_DEACTIVATE,
            timestamp=datetime.now(),
            user_id=self.user_id,
            data={'username': self.user.username if self.user else 'unknown'}
        )
        event_handler.emit_event(deactivate_event)
        
        self.logger.info(f"用户监控已停止: 用户 {self.user_id}")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running and self.monitor_thread and self.monitor_thread.is_alive()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.stats.copy()
            stats.update({
                'user_id': self.user_id,
                'username': self.user.username if self.user else None,
                'running': self.running,
                'last_check_time': self.last_check_time.isoformat(),
                'strategy_manager_stats': self.strategy_manager.get_statistics(),
                'order_manager_stats': self.order_manager.get_order_statistics(),
                'active_orders_count': len(self.order_manager.get_active_orders()),
                'total_orders_count': len(self.order_manager.get_all_orders())
            })
            
            if stats['start_time']:
                stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
            
            return stats
    
    def force_strategy_check(self) -> bool:
        """强制检查策略状态"""
        try:
            return self._check_user_strategies()
        except Exception as e:
            self.logger.error(f"强制检查策略失败: {e}")
            return False
    
    def force_order_check(self) -> None:
        """强制检查订单状态"""
        try:
            self._check_user_orders()
        except Exception as e:
            self.logger.error(f"强制检查订单失败: {e}")
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            # 停止监控
            self.stop()
            
            # 清理组件
            self.strategy_manager.cleanup()
            self.order_manager.cleanup()
            
            self.logger.info(f"用户监控器清理完成: 用户 {self.user_id}")
            
        except Exception as e:
            self.logger.error(f"用户监控器清理失败: {e}")
    
    def __repr__(self):
        return f"<UserMonitor(user_id={self.user_id}, running={self.running})>"