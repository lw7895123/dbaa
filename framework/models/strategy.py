# -*- coding: utf-8 -*-
"""
策略数据模型
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json


class UserStrategy:
    """用户策略模型类"""
    
    # 策略状态常量
    STATUS_DISABLED = 0     # 关闭
    STATUS_ENABLED = 1      # 开启
    STATUS_PAUSED = 2       # 暂停
    
    def __init__(self, id: int = None, user_id: int = None, strategy_name: str = None,
                 strategy_type: str = None, status: int = STATUS_ENABLED,
                 config: Dict = None, risk_config: Dict = None,
                 performance_data: Dict = None, start_time: datetime = None,
                 end_time: datetime = None, created_at: datetime = None,
                 updated_at: datetime = None):
        self.id = id
        self.user_id = user_id
        self.strategy_name = strategy_name
        self.strategy_type = strategy_type
        self.status = status
        self.config = config or {}
        self.risk_config = risk_config or {}
        self.performance_data = performance_data or {}
        self.start_time = start_time
        self.end_time = end_time
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'status': self.status,
            'config': self.config,
            'risk_config': self.risk_config,
            'performance_data': self.performance_data,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserStrategy':
        """从字典创建策略对象"""
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            strategy_name=data.get('strategy_name'),
            strategy_type=data.get('strategy_type'),
            status=data.get('status', cls.STATUS_ENABLED),
            config=data.get('config', {}),
            risk_config=data.get('risk_config', {}),
            performance_data=data.get('performance_data', {}),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def is_active(self) -> bool:
        """检查策略是否激活"""
        return self.status == self.STATUS_ENABLED
    
    def is_paused(self) -> bool:
        """检查策略是否暂停"""
        return self.status == self.STATUS_PAUSED
    
    def is_disabled(self) -> bool:
        """检查策略是否关闭"""
        return self.status == self.STATUS_DISABLED
    
    def enable(self):
        """启用策略"""
        self.status = self.STATUS_ENABLED
        if not self.start_time:
            self.start_time = datetime.now()
        self.updated_at = datetime.now()
    
    def disable(self):
        """禁用策略"""
        self.status = self.STATUS_DISABLED
        self.end_time = datetime.now()
        self.updated_at = datetime.now()
    
    def pause(self):
        """暂停策略"""
        self.status = self.STATUS_PAUSED
        self.updated_at = datetime.now()
    
    def resume(self):
        """恢复策略"""
        if self.status == self.STATUS_PAUSED:
            self.status = self.STATUS_ENABLED
            self.updated_at = datetime.now()
    
    def update_config(self, config: Dict[str, Any]):
        """更新策略配置"""
        self.config.update(config)
        self.updated_at = datetime.now()
    
    def update_risk_config(self, risk_config: Dict[str, Any]):
        """更新风控配置"""
        self.risk_config.update(risk_config)
        self.updated_at = datetime.now()
    
    def update_performance(self, performance_data: Dict[str, Any]):
        """更新策略表现数据"""
        self.performance_data.update(performance_data)
        self.updated_at = datetime.now()
    
    def get_status_name(self) -> str:
        """获取状态名称"""
        status_names = {
            self.STATUS_DISABLED: "关闭",
            self.STATUS_ENABLED: "开启",
            self.STATUS_PAUSED: "暂停"
        }
        return status_names.get(self.status, "未知")
    
    def get_config_value(self, key: str, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def get_risk_config_value(self, key: str, default=None):
        """获取风控配置值"""
        return self.risk_config.get(key, default)
    
    def is_time_valid(self) -> bool:
        """检查策略时间是否有效"""
        now = datetime.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True
    
    def __repr__(self):
        return (f"<UserStrategy(id={self.id}, user_id={self.user_id}, "
                f"name='{self.strategy_name}', status={self.get_status_name()})>")