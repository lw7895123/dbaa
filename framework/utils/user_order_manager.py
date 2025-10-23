# -*- coding: utf-8 -*-
"""
用户订单管理器
负责管理单个用户的所有订单操作
"""
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
from datetime import datetime
from ..models import Order, User
from ..database import mysql_manager, redis_manager
from ..config import CACHE_CONFIG
from ..logging import get_user_logger


class UserOrderManager:
    """用户订单管理器"""
    
    def __init__(self, user_id: int):
        """
        初始化用户订单管理器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.orders = {}  # {order_id: Order}
        self.active_orders = {}  # {order_id: Order} 活跃订单缓存
        self.logger = get_user_logger(user_id)
        self.lock = threading.RLock()
        self.last_update_time = datetime.now()
        
        # 订单更新回调函数列表
        self.order_update_callbacks = []  # List[Callable[[Order], None]]
        
        self.logger.info(f"用户订单管理器初始化: 用户 {user_id}")
    
    def add_order_update_callback(self, callback: Callable[[Order], None]) -> None:
        """添加订单更新回调函数"""
        self.order_update_callbacks.append(callback)
    
    def remove_order_update_callback(self, callback: Callable[[Order], None]) -> None:
        """移除订单更新回调函数"""
        if callback in self.order_update_callbacks:
            self.order_update_callbacks.remove(callback)
    
    def _notify_order_update(self, order: Order) -> None:
        """通知订单更新"""
        for callback in self.order_update_callbacks:
            try:
                callback(order)
            except Exception as e:
                self.logger.error(f"订单更新回调执行失败: {e}")
    
    def load_orders(self, force_reload: bool = False) -> bool:
        """
        加载用户订单
        
        Args:
            force_reload: 是否强制从数据库重新加载
            
        Returns:
            bool: 加载是否成功
        """
        try:
            orders_data = None
            
            if not force_reload:
                # 先尝试从Redis缓存获取
                orders_data = redis_manager.get_cached_user_orders(self.user_id)
                if orders_data:
                    self.logger.debug(f"从缓存加载订单: 用户 {self.user_id}")
            
            if not orders_data:
                # 从MySQL获取
                orders_data = mysql_manager.get_user_orders(self.user_id, limit=5000)
                if orders_data:
                    # 缓存到Redis
                    redis_manager.cache_user_orders(self.user_id, orders_data)
                    self.logger.debug(f"从数据库加载订单: 用户 {self.user_id}")
            
            if not orders_data:
                self.logger.info(f"用户 {self.user_id} 没有订单")
                return True
            
            # 转换为Order对象
            with self.lock:
                self.orders.clear()
                self.active_orders.clear()
                
                for order_data in orders_data:
                    order = Order.from_dict(order_data)
                    self.orders[order.id] = order
                    
                    # 缓存活跃订单
                    if order.is_active():
                        self.active_orders[order.id] = order
                
                self.last_update_time = datetime.now()
            
            self.logger.info(f"加载订单完成: 用户 {self.user_id}, 总订单 {len(self.orders)}, 活跃订单 {len(self.active_orders)}")
            return True
            
        except Exception as e:
            self.logger.error(f"加载订单失败: 用户 {self.user_id}, 错误: {e}")
            return False
    
    def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """根据ID获取订单"""
        with self.lock:
            return self.orders.get(order_id)
    
    def get_order_by_no(self, order_no: str) -> Optional[Order]:
        """根据订单号获取订单"""
        with self.lock:
            for order in self.orders.values():
                if order.order_no == order_no:
                    return order
            return None
    
    def get_orders_by_strategy(self, strategy_id: int) -> List[Order]:
        """获取指定策略的订单"""
        with self.lock:
            return [order for order in self.orders.values() if order.strategy_id == strategy_id]
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """获取指定标的的订单"""
        with self.lock:
            return [order for order in self.orders.values() if order.symbol == symbol]
    
    def get_orders_by_status(self, status: int) -> List[Order]:
        """获取指定状态的订单"""
        with self.lock:
            return [order for order in self.orders.values() if order.status == status]
    
    def get_active_orders(self) -> List[Order]:
        """获取所有活跃订单"""
        with self.lock:
            return list(self.active_orders.values())
    
    def get_all_orders(self) -> List[Order]:
        """获取所有订单"""
        with self.lock:
            return list(self.orders.values())
    
    def add_order(self, order: Order) -> bool:
        """
        添加新订单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 添加是否成功
        """
        try:
            with self.lock:
                # 添加到内存缓存
                self.orders[order.id] = order
                
                # 如果是活跃订单，添加到活跃订单缓存
                if order.is_active():
                    self.active_orders[order.id] = order
                
                self.last_update_time = datetime.now()
            
            # 清除Redis缓存，强制下次从数据库重新加载
            redis_manager.delete(f"{redis_manager.config['user_orders_prefix']}{self.user_id}")
            
            self.logger.info(f"添加订单: {order.order_no}, 状态: {order.get_status_name()}")
            
            # 通知订单更新
            self._notify_order_update(order)
            
            return True
            
        except Exception as e:
            self.logger.error(f"添加订单失败: {order.order_no}, 错误: {e}")
            return False
    
    def update_order(self, order_id: int, **kwargs) -> bool:
        """
        更新订单信息
        
        Args:
            order_id: 订单ID
            **kwargs: 要更新的字段
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with self.lock:
                order = self.orders.get(order_id)
                if not order:
                    self.logger.warning(f"订单不存在: ID {order_id}")
                    return False
                
                # 更新订单字段
                old_status = order.status
                old_active = order.is_active()
                
                for key, value in kwargs.items():
                    if hasattr(order, key):
                        setattr(order, key, value)
                
                order.update_time = datetime.now()
                
                # 更新活跃订单缓存
                new_active = order.is_active()
                if old_active and not new_active:
                    # 从活跃订单中移除
                    self.active_orders.pop(order_id, None)
                elif not old_active and new_active:
                    # 添加到活跃订单
                    self.active_orders[order_id] = order
                
                self.last_update_time = datetime.now()
            
            # 更新数据库
            success = mysql_manager.update_order_status(
                order_id=order_id,
                status=kwargs.get('status', order.status),
                filled_quantity=float(kwargs.get('filled_quantity', order.filled_quantity)),
                avg_price=float(kwargs.get('avg_price', order.avg_price)) if order.avg_price else None,
                commission=float(kwargs.get('commission', order.commission))
            )
            
            if success:
                # 清除Redis缓存
                redis_manager.delete(f"{redis_manager.config['user_orders_prefix']}{self.user_id}")
                
                self.logger.info(f"更新订单: {order.order_no}, 状态: {old_status} -> {order.status}")
                
                # 通知订单更新
                self._notify_order_update(order)
                
                return True
            else:
                self.logger.error(f"数据库更新订单失败: ID {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新订单失败: ID {order_id}, 错误: {e}")
            return False
    
    def update_order_fill(self, order_id: int, filled_quantity: Decimal, 
                         avg_price: Optional[Decimal] = None, 
                         commission: Optional[Decimal] = None) -> bool:
        """
        更新订单成交信息
        
        Args:
            order_id: 订单ID
            filled_quantity: 成交数量
            avg_price: 平均成交价格
            commission: 手续费
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with self.lock:
                order = self.orders.get(order_id)
                if not order:
                    self.logger.warning(f"订单不存在: ID {order_id}")
                    return False
                
                # 更新成交信息
                order.update_fill(filled_quantity, avg_price, commission)
                
                # 更新活跃订单缓存
                if order.is_completed():
                    self.active_orders.pop(order_id, None)
                
                self.last_update_time = datetime.now()
            
            # 更新数据库
            success = mysql_manager.update_order_status(
                order_id=order_id,
                status=order.status,
                filled_quantity=float(filled_quantity),
                avg_price=float(avg_price) if avg_price else None,
                commission=float(commission) if commission else None
            )
            
            if success:
                # 清除Redis缓存
                redis_manager.delete(f"{redis_manager.config['user_orders_prefix']}{self.user_id}")
                
                self.logger.info(f"更新订单成交: {order.order_no}, 成交量: {filled_quantity}, 状态: {order.get_status_name()}")
                
                # 通知订单更新
                self._notify_order_update(order)
                
                return True
            else:
                self.logger.error(f"数据库更新订单成交失败: ID {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新订单成交失败: ID {order_id}, 错误: {e}")
            return False
    
    def cancel_order(self, order_id: int) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 取消是否成功
        """
        try:
            with self.lock:
                order = self.orders.get(order_id)
                if not order:
                    self.logger.warning(f"订单不存在: ID {order_id}")
                    return False
                
                if not order.is_active():
                    self.logger.warning(f"订单不是活跃状态，无法取消: {order.order_no}")
                    return False
                
                # 取消订单
                order.cancel()
                
                # 从活跃订单中移除
                self.active_orders.pop(order_id, None)
                
                self.last_update_time = datetime.now()
            
            # 更新数据库
            success = mysql_manager.update_order_status(order_id, Order.STATUS_CANCELLED)
            
            if success:
                # 清除Redis缓存
                redis_manager.delete(f"{redis_manager.config['user_orders_prefix']}{self.user_id}")
                
                self.logger.info(f"取消订单: {order.order_no}")
                
                # 通知订单更新
                self._notify_order_update(order)
                
                return True
            else:
                self.logger.error(f"数据库取消订单失败: ID {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"取消订单失败: ID {order_id}, 错误: {e}")
            return False
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """获取订单统计信息"""
        with self.lock:
            total_orders = len(self.orders)
            active_orders = len(self.active_orders)
            
            status_count = {}
            symbol_count = {}
            strategy_count = {}
            
            for order in self.orders.values():
                # 状态统计
                status_name = order.get_status_name()
                status_count[status_name] = status_count.get(status_name, 0) + 1
                
                # 标的统计
                symbol_count[order.symbol] = symbol_count.get(order.symbol, 0) + 1
                
                # 策略统计
                strategy_count[order.strategy_id] = strategy_count.get(order.strategy_id, 0) + 1
            
            return {
                'user_id': self.user_id,
                'total_orders': total_orders,
                'active_orders': active_orders,
                'status_distribution': status_count,
                'symbol_distribution': symbol_count,
                'strategy_distribution': strategy_count,
                'last_update_time': self.last_update_time.isoformat()
            }
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            with self.lock:
                self.orders.clear()
                self.active_orders.clear()
                self.order_update_callbacks.clear()
            
            self.logger.info(f"用户订单管理器清理完成: 用户 {self.user_id}")
        except Exception as e:
            self.logger.error(f"用户订单管理器清理失败: 用户 {self.user_id}, 错误: {e}")
    
    def __len__(self):
        """返回订单总数"""
        return len(self.orders)
    
    def __contains__(self, order_id):
        """检查是否包含指定订单"""
        return order_id in self.orders
    
    def __repr__(self):
        return f"<UserOrderManager(user_id={self.user_id}, orders={len(self.orders)}, active={len(self.active_orders)})>"