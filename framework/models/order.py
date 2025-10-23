# -*- coding: utf-8 -*-
"""
订单数据模型
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
import json


class Order:
    """订单模型类"""
    
    # 订单类型常量
    ORDER_TYPE_BUY = 1
    ORDER_TYPE_SELL = 2
    
    # 订单状态常量
    STATUS_PENDING = 0      # 待处理
    STATUS_PARTIAL = 1      # 部分成交
    STATUS_FILLED = 2       # 完全成交
    STATUS_CANCELLED = 3    # 已取消
    STATUS_FAILED = 4       # 失败
    
    def __init__(self, id: int = None, user_id: int = None, strategy_id: int = None,
                 order_no: str = None, symbol: str = None, order_type: int = None,
                 quantity: Decimal = None, price: Decimal = None, status: int = STATUS_PENDING,
                 filled_quantity: Decimal = None, avg_price: Decimal = None,
                 commission: Decimal = None, order_time: datetime = None,
                 update_time: datetime = None, extra_data: Dict = None):
        self.id = id
        self.user_id = user_id
        self.strategy_id = strategy_id
        self.order_no = order_no
        self.symbol = symbol
        self.order_type = order_type
        self.quantity = quantity or Decimal('0')
        self.price = price or Decimal('0')
        self.status = status
        self.filled_quantity = filled_quantity or Decimal('0')
        self.avg_price = avg_price
        self.commission = commission or Decimal('0')
        self.order_time = order_time or datetime.now()
        self.update_time = update_time or datetime.now()
        self.extra_data = extra_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'strategy_id': self.strategy_id,
            'order_no': self.order_no,
            'symbol': self.symbol,
            'order_type': self.order_type,
            'quantity': str(self.quantity),
            'price': str(self.price),
            'status': self.status,
            'filled_quantity': str(self.filled_quantity),
            'avg_price': str(self.avg_price) if self.avg_price else None,
            'commission': str(self.commission),
            'order_time': self.order_time.isoformat() if self.order_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None,
            'extra_data': self.extra_data,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """从字典创建订单对象"""
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            strategy_id=data.get('strategy_id'),
            order_no=data.get('order_no'),
            symbol=data.get('symbol'),
            order_type=data.get('order_type'),
            quantity=Decimal(str(data.get('quantity', '0'))),
            price=Decimal(str(data.get('price', '0'))),
            status=data.get('status', cls.STATUS_PENDING),
            filled_quantity=Decimal(str(data.get('filled_quantity', '0'))),
            avg_price=Decimal(str(data.get('avg_price'))) if data.get('avg_price') else None,
            commission=Decimal(str(data.get('commission', '0'))),
            order_time=data.get('order_time'),
            update_time=data.get('update_time'),
            extra_data=data.get('extra_data', {})
        )
    
    def is_active(self) -> bool:
        """检查订单是否活跃（需要监控）"""
        return self.status in [self.STATUS_PENDING, self.STATUS_PARTIAL]
    
    def is_completed(self) -> bool:
        """检查订单是否已完成"""
        return self.status in [self.STATUS_FILLED, self.STATUS_CANCELLED, self.STATUS_FAILED]
    
    def get_remaining_quantity(self) -> Decimal:
        """获取剩余数量"""
        return self.quantity - self.filled_quantity
    
    def get_fill_percentage(self) -> float:
        """获取成交百分比"""
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)
    
    def update_fill(self, filled_qty: Decimal, avg_price: Decimal = None, commission: Decimal = None):
        """更新成交信息"""
        self.filled_quantity = filled_qty
        if avg_price:
            self.avg_price = avg_price
        if commission:
            self.commission = commission
        
        # 更新状态
        if self.filled_quantity >= self.quantity:
            self.status = self.STATUS_FILLED
        elif self.filled_quantity > 0:
            self.status = self.STATUS_PARTIAL
        
        self.update_time = datetime.now()
    
    def cancel(self):
        """取消订单"""
        if self.is_active():
            self.status = self.STATUS_CANCELLED
            self.update_time = datetime.now()
    
    def get_order_type_name(self) -> str:
        """获取订单类型名称"""
        return "买入" if self.order_type == self.ORDER_TYPE_BUY else "卖出"
    
    def get_status_name(self) -> str:
        """获取状态名称"""
        status_names = {
            self.STATUS_PENDING: "待处理",
            self.STATUS_PARTIAL: "部分成交",
            self.STATUS_FILLED: "完全成交",
            self.STATUS_CANCELLED: "已取消",
            self.STATUS_FAILED: "失败"
        }
        return status_names.get(self.status, "未知")
    
    def __repr__(self):
        return (f"<Order(id={self.id}, order_no='{self.order_no}', "
                f"symbol='{self.symbol}', status={self.get_status_name()})>")