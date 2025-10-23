# -*- coding: utf-8 -*-
"""
策略管理器
负责管理用户的所有策略实例
"""
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from ..models import UserStrategy, Order
from ..database import mysql_manager, redis_manager
from ..logging import get_user_logger
from .base_strategy import BaseStrategy, StrategyFactory


class StrategyManager:
    """策略管理器"""
    
    def __init__(self, user_id: int):
        """
        初始化策略管理器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.strategies = {}  # {strategy_id: BaseStrategy}
        self.logger = get_user_logger(user_id)
        self.is_running = False
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix=f"strategy_user_{user_id}")
        
        self.logger.info(f"策略管理器初始化: 用户 {user_id}")
    
    def load_strategies(self) -> bool:
        """从数据库加载用户策略"""
        try:
            # 先尝试从Redis缓存获取
            cached_strategies = redis_manager.get_cached_user_strategies(self.user_id)
            
            if cached_strategies:
                strategies_data = cached_strategies
                self.logger.debug(f"从缓存加载策略: 用户 {self.user_id}")
            else:
                # 从MySQL获取
                strategies_data = mysql_manager.get_user_strategies(self.user_id, status=1)  # 只获取启用的策略
                if strategies_data:
                    # 缓存到Redis
                    redis_manager.cache_user_strategies(self.user_id, strategies_data)
                    self.logger.debug(f"从数据库加载策略: 用户 {self.user_id}")
            
            if not strategies_data:
                self.logger.warning(f"用户 {self.user_id} 没有启用的策略")
                return False
            
            # 创建策略实例
            with self.lock:
                for strategy_data in strategies_data:
                    strategy_config = UserStrategy.from_dict(strategy_data)
                    strategy_instance = StrategyFactory.create_strategy(self.user_id, strategy_config)
                    
                    if strategy_instance:
                        self.strategies[strategy_config.id] = strategy_instance
                        self.logger.info(f"加载策略: {strategy_config.strategy_name} (ID: {strategy_config.id})")
                    else:
                        self.logger.error(f"创建策略实例失败: {strategy_config.strategy_name}")
            
            return len(self.strategies) > 0
            
        except Exception as e:
            self.logger.error(f"加载策略失败: 用户 {self.user_id}, 错误: {e}")
            return False
    
    def start_all_strategies(self) -> bool:
        """启动所有策略"""
        if not self.strategies:
            self.logger.warning(f"用户 {self.user_id} 没有可启动的策略")
            return False
        
        success_count = 0
        with self.lock:
            for strategy_id, strategy in self.strategies.items():
                try:
                    if strategy.start():
                        success_count += 1
                        self.logger.info(f"策略启动成功: {strategy.strategy_name}")
                    else:
                        self.logger.error(f"策略启动失败: {strategy.strategy_name}")
                except Exception as e:
                    self.logger.error(f"策略启动异常: {strategy.strategy_name}, 错误: {e}")
        
        self.is_running = success_count > 0
        if self.is_running:
            redis_manager.add_active_user(self.user_id)
            self.logger.info(f"用户 {self.user_id} 策略管理器启动成功，成功启动 {success_count}/{len(self.strategies)} 个策略")
        
        return self.is_running
    
    def stop_all_strategies(self) -> None:
        """停止所有策略"""
        with self.lock:
            for strategy_id, strategy in self.strategies.items():
                try:
                    strategy.stop()
                    self.logger.info(f"策略停止: {strategy.strategy_name}")
                except Exception as e:
                    self.logger.error(f"策略停止异常: {strategy.strategy_name}, 错误: {e}")
        
        self.is_running = False
        redis_manager.remove_active_user(self.user_id)
        self.logger.info(f"用户 {self.user_id} 所有策略已停止")
    
    def add_strategy(self, strategy_config: UserStrategy) -> bool:
        """添加新策略"""
        try:
            strategy_instance = StrategyFactory.create_strategy(self.user_id, strategy_config)
            if strategy_instance:
                with self.lock:
                    self.strategies[strategy_config.id] = strategy_instance
                    if self.is_running and strategy_instance.start():
                        self.logger.info(f"新策略添加并启动: {strategy_config.strategy_name}")
                        return True
                    else:
                        self.logger.info(f"新策略添加: {strategy_config.strategy_name}")
                        return True
            return False
        except Exception as e:
            self.logger.error(f"添加策略失败: {strategy_config.strategy_name}, 错误: {e}")
            return False
    
    def remove_strategy(self, strategy_id: int) -> bool:
        """移除策略"""
        try:
            with self.lock:
                if strategy_id in self.strategies:
                    strategy = self.strategies.pop(strategy_id)
                    strategy.stop()
                    self.logger.info(f"策略移除: {strategy.strategy_name}")
                    
                    # 如果没有策略了，停止管理器
                    if not self.strategies:
                        self.is_running = False
                        redis_manager.remove_active_user(self.user_id)
                        self.logger.info(f"用户 {self.user_id} 所有策略已移除，管理器停止")
                    
                    return True
                else:
                    self.logger.warning(f"策略不存在: ID {strategy_id}")
                    return False
        except Exception as e:
            self.logger.error(f"移除策略失败: ID {strategy_id}, 错误: {e}")
            return False
    
    def update_strategy_status(self, strategy_id: int, status: int) -> bool:
        """更新策略状态"""
        try:
            with self.lock:
                if strategy_id in self.strategies:
                    strategy = self.strategies[strategy_id]
                    
                    if status == 1:  # 启用
                        if not strategy.is_running:
                            success = strategy.start()
                            self.logger.info(f"策略启用: {strategy.strategy_name}, 结果: {success}")
                            return success
                    elif status == 0:  # 禁用
                        if strategy.is_running:
                            strategy.stop()
                            self.logger.info(f"策略禁用: {strategy.strategy_name}")
                            return True
                    elif status == 2:  # 暂停
                        # 暂停逻辑可以根据需要实现
                        self.logger.info(f"策略暂停: {strategy.strategy_name}")
                        return True
                    
                    return True
                else:
                    self.logger.warning(f"策略不存在: ID {strategy_id}")
                    return False
        except Exception as e:
            self.logger.error(f"更新策略状态失败: ID {strategy_id}, 错误: {e}")
            return False
    
    def process_order_update(self, order: Order) -> None:
        """处理订单更新"""
        try:
            strategy_id = order.strategy_id
            with self.lock:
                if strategy_id in self.strategies:
                    strategy = self.strategies[strategy_id]
                    # 异步处理订单更新
                    self.executor.submit(strategy.on_order_update, order)
                else:
                    self.logger.warning(f"订单对应的策略不存在: 策略ID {strategy_id}, 订单 {order.order_no}")
        except Exception as e:
            self.logger.error(f"处理订单更新失败: 订单 {order.order_no}, 错误: {e}")
    
    def process_market_data(self, symbol: str, market_data: Dict[str, Any]) -> None:
        """处理市场数据"""
        try:
            with self.lock:
                for strategy in self.strategies.values():
                    if strategy.is_running:
                        # 异步处理市场数据
                        self.executor.submit(strategy.on_market_data, symbol, market_data)
        except Exception as e:
            self.logger.error(f"处理市场数据失败: {symbol}, 错误: {e}")
    
    def run_timer_callbacks(self) -> None:
        """运行定时器回调"""
        try:
            with self.lock:
                for strategy in self.strategies.values():
                    if strategy.is_running:
                        # 异步执行定时器回调
                        self.executor.submit(strategy.on_timer)
        except Exception as e:
            self.logger.error(f"运行定时器回调失败: 错误: {e}")
    
    def check_strategies_status(self) -> bool:
        """检查策略状态，如果没有活跃策略则返回False"""
        try:
            # 从数据库检查策略状态
            active_strategies = mysql_manager.get_user_strategies(self.user_id, status=1)
            
            if not active_strategies:
                self.logger.info(f"用户 {self.user_id} 没有活跃策略，准备停止")
                return False
            
            # 检查当前运行的策略是否还在数据库中
            active_strategy_ids = {s['id'] for s in active_strategies}
            
            with self.lock:
                current_strategy_ids = set(self.strategies.keys())
                
                # 移除不再活跃的策略
                for strategy_id in current_strategy_ids - active_strategy_ids:
                    self.remove_strategy(strategy_id)
                
                # 添加新的活跃策略
                for strategy_data in active_strategies:
                    strategy_id = strategy_data['id']
                    if strategy_id not in self.strategies:
                        strategy_config = UserStrategy.from_dict(strategy_data)
                        self.add_strategy(strategy_config)
            
            return len(self.strategies) > 0
            
        except Exception as e:
            self.logger.error(f"检查策略状态失败: 用户 {self.user_id}, 错误: {e}")
            return False
    
    def get_strategies_info(self) -> List[Dict[str, Any]]:
        """获取所有策略信息"""
        with self.lock:
            return [strategy.get_strategy_info() for strategy in self.strategies.values()]
    
    def get_strategy_by_id(self, strategy_id: int) -> Optional[BaseStrategy]:
        """根据ID获取策略"""
        with self.lock:
            return self.strategies.get(strategy_id)
    
    def get_all_orders(self) -> List[Order]:
        """获取所有策略的订单"""
        all_orders = []
        with self.lock:
            for strategy in self.strategies.values():
                all_orders.extend(strategy.get_orders())
        return all_orders
    
    def get_active_orders(self) -> List[Order]:
        """获取所有活跃订单"""
        active_orders = []
        with self.lock:
            for strategy in self.strategies.values():
                active_orders.extend(strategy.get_active_orders())
        return active_orders
    
    def is_strategy_running(self, strategy_id: int) -> bool:
        """检查指定策略是否正在运行"""
        with self.lock:
            strategy = self.strategies.get(strategy_id)
            if strategy:
                return strategy.is_running()
            return False
    
    def handle_order_update(self, order: Order) -> None:
        """处理订单更新"""
        try:
            with self.lock:
                # 找到对应的策略并处理订单更新
                strategy = self.strategies.get(order.strategy_id)
                if strategy:
                    strategy.on_order_update(order)
                    self.logger.debug(f"订单更新已处理: 策略 {order.strategy_id}, 订单 {order.id}")
                else:
                    self.logger.warning(f"未找到策略 {order.strategy_id} 来处理订单更新 {order.id}")
        except Exception as e:
            self.logger.error(f"处理订单更新失败: 订单 {order.id}, 错误: {e}")
    
    def start_strategy(self, strategy_config: UserStrategy) -> bool:
        """启动指定策略"""
        try:
            # 如果策略已存在，直接启动
            if strategy_config.id in self.strategies:
                strategy = self.strategies[strategy_config.id]
                if strategy.start():
                    self.logger.info(f"策略启动成功: {strategy_config.strategy_name}")
                    return True
                else:
                    self.logger.error(f"策略启动失败: {strategy_config.strategy_name}")
                    return False
            else:
                # 策略不存在，先添加再启动
                return self.add_strategy(strategy_config)
        except Exception as e:
            self.logger.error(f"启动策略失败: {strategy_config.strategy_name}, 错误: {e}")
            return False

    def stop_strategy(self, strategy_id: int) -> bool:
        """停止指定策略"""
        try:
            with self.lock:
                if strategy_id in self.strategies:
                    strategy = self.strategies[strategy_id]
                    strategy.stop()
                    self.logger.info(f"策略停止成功: {strategy.strategy_name}")
                    return True
                else:
                    self.logger.warning(f"策略不存在，无法停止: ID {strategy_id}")
                    return False
        except Exception as e:
            self.logger.error(f"停止策略失败: ID {strategy_id}, 错误: {e}")
            return False

    def get_running_strategy_ids(self) -> List[int]:
        """获取所有正在运行的策略ID"""
        try:
            with self.lock:
                running_ids = []
                for strategy_id, strategy in self.strategies.items():
                    if hasattr(strategy, 'is_running') and strategy.is_running():
                        running_ids.append(strategy_id)
                    elif hasattr(strategy, 'running') and strategy.running:
                        running_ids.append(strategy_id)
                return running_ids
        except Exception as e:
            self.logger.error(f"获取运行中策略ID失败: {e}")
            return []

    def cleanup(self) -> None:
        """清理资源"""
        try:
            self.stop_all_strategies()
            self.executor.shutdown(wait=True)
            redis_manager.clear_user_cache(self.user_id)
            self.logger.info(f"用户 {self.user_id} 策略管理器清理完成")
        except Exception as e:
            self.logger.error(f"策略管理器清理失败: 用户 {self.user_id}, 错误: {e}")
    
    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except:
            pass