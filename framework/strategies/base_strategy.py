# -*- coding: utf-8 -*-
"""
策略抽象基类
所有策略都必须继承此基类并实现相应方法
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from ..models import Order, UserStrategy


class BaseStrategy(ABC):
    """策略抽象基类"""
    
    def __init__(self, user_id: int, strategy_config: UserStrategy):
        """
        初始化策略
        
        Args:
            user_id: 用户ID
            strategy_config: 策略配置对象
        """
        self.user_id = user_id
        self.strategy_config = strategy_config
        self.strategy_id = strategy_config.id
        self.strategy_name = strategy_config.strategy_name
        self.strategy_type = strategy_config.strategy_type
        self.config = strategy_config.config
        self.risk_config = strategy_config.risk_config
        self.performance_data = strategy_config.performance_data
        
        self.logger = logging.getLogger(f"{__name__}.{self.strategy_type}")
        self.is_running = False
        self.last_update_time = datetime.now()
        
        # 策略状态
        self._orders = {}  # 策略管理的订单 {order_id: Order}
        self._positions = {}  # 持仓信息
        self._performance_metrics = {}  # 性能指标
        
        self.logger.info(f"策略初始化: {self.strategy_name} (ID: {self.strategy_id})")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化策略
        在策略开始运行前调用，用于设置初始状态
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    def on_order_update(self, order: Order) -> None:
        """
        订单更新回调
        当订单状态发生变化时调用
        
        Args:
            order: 更新的订单对象
        """
        pass
    
    @abstractmethod
    def on_market_data(self, symbol: str, market_data: Dict[str, Any]) -> None:
        """
        市场数据回调
        当接收到市场数据时调用
        
        Args:
            symbol: 交易标的
            market_data: 市场数据
        """
        pass
    
    @abstractmethod
    def on_timer(self) -> None:
        """
        定时器回调
        定期调用，用于执行策略逻辑
        """
        pass
    
    @abstractmethod
    def on_risk_check(self) -> bool:
        """
        风控检查
        在执行交易前进行风控检查
        
        Returns:
            bool: 是否通过风控检查
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        清理资源
        策略停止时调用，用于清理资源
        """
        pass
    
    def start(self) -> bool:
        """启动策略"""
        try:
            if self.initialize():
                self.is_running = True
                self.logger.info(f"策略启动成功: {self.strategy_name}")
                return True
            else:
                self.logger.error(f"策略初始化失败: {self.strategy_name}")
                return False
        except Exception as e:
            self.logger.error(f"策略启动失败: {self.strategy_name}, 错误: {e}")
            return False
    
    def stop(self) -> None:
        """停止策略"""
        try:
            self.is_running = False
            self.cleanup()
            self.logger.info(f"策略停止: {self.strategy_name}")
        except Exception as e:
            self.logger.error(f"策略停止失败: {self.strategy_name}, 错误: {e}")
    
    def add_order(self, order: Order) -> None:
        """添加订单到策略管理"""
        self._orders[order.id] = order
        self.logger.debug(f"添加订单到策略: {order.order_no}")
    
    def remove_order(self, order_id: int) -> None:
        """从策略管理中移除订单"""
        if order_id in self._orders:
            order = self._orders.pop(order_id)
            self.logger.debug(f"从策略移除订单: {order.order_no}")
    
    def get_orders(self) -> List[Order]:
        """获取策略管理的所有订单"""
        return list(self._orders.values())
    
    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return [order for order in self._orders.values() if order.is_active()]
    
    def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """根据ID获取订单"""
        return self._orders.get(order_id)
    
    def update_performance(self, metrics: Dict[str, Any]) -> None:
        """更新性能指标"""
        self._performance_metrics.update(metrics)
        self.last_update_time = datetime.now()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self._performance_metrics.copy()
    
    def get_config_value(self, key: str, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def get_risk_config_value(self, key: str, default=None):
        """获取风控配置值"""
        return self.risk_config.get(key, default)
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新策略配置"""
        self.config.update(config)
        self.logger.info(f"策略配置已更新: {self.strategy_name}")
    
    def update_risk_config(self, risk_config: Dict[str, Any]) -> None:
        """更新风控配置"""
        self.risk_config.update(risk_config)
        self.logger.info(f"策略风控配置已更新: {self.strategy_name}")
    
    def is_strategy_active(self) -> bool:
        """检查策略是否激活"""
        return self.is_running and self.strategy_config.is_active()
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        return {
            'strategy_id': self.strategy_id,
            'user_id': self.user_id,
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'is_running': self.is_running,
            'is_active': self.is_strategy_active(),
            'order_count': len(self._orders),
            'active_order_count': len(self.get_active_orders()),
            'last_update_time': self.last_update_time.isoformat(),
            'performance_metrics': self._performance_metrics
        }
    
    def __repr__(self):
        return (f"<{self.__class__.__name__}(id={self.strategy_id}, "
                f"name='{self.strategy_name}', running={self.is_running})>")


class StrategyFactory:
    """策略工厂类"""
    
    _strategy_classes = {}
    
    @classmethod
    def register_strategy(cls, strategy_type: str, strategy_class):
        """注册策略类"""
        cls._strategy_classes[strategy_type] = strategy_class
    
    @classmethod
    def create_strategy(cls, user_id: int, strategy_config: UserStrategy) -> Optional[BaseStrategy]:
        """创建策略实例"""
        strategy_type = strategy_config.strategy_type
        strategy_class = cls._strategy_classes.get(strategy_type)
        
        if strategy_class:
            return strategy_class(user_id, strategy_config)
        else:
            logging.error(f"未知的策略类型: {strategy_type}")
            return None
    
    @classmethod
    def get_registered_strategies(cls) -> List[str]:
        """获取已注册的策略类型"""
        return list(cls._strategy_classes.keys())


# 示例策略实现（仅作为参考）
class ExampleStrategy(BaseStrategy):
    """示例策略实现"""
    
    def initialize(self) -> bool:
        """初始化策略"""
        self.logger.info("示例策略初始化")
        return True
    
    def on_order_update(self, order: Order) -> None:
        """订单更新回调"""
        self.logger.info(f"订单更新: {order.order_no}, 状态: {order.get_status_name()}")
    
    def on_market_data(self, symbol: str, market_data: Dict[str, Any]) -> None:
        """市场数据回调"""
        self.logger.debug(f"接收市场数据: {symbol}, 数据: {market_data}")
    
    def on_timer(self) -> None:
        """定时器回调"""
        self.logger.debug("定时器触发")
    
    def on_risk_check(self) -> bool:
        """风控检查"""
        return True
    
    def cleanup(self) -> None:
        """清理资源"""
        self.logger.info("示例策略清理")


# 注册示例策略
StrategyFactory.register_strategy('example', ExampleStrategy)