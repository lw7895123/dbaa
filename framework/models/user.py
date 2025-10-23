# -*- coding: utf-8 -*-
"""
用户数据模型
"""
from datetime import datetime
from typing import Optional, Dict, Any


class User:
    """用户模型类"""
    
    def __init__(self, id: int = None, username: str = None, email: str = None, 
                 phone: str = None, status: int = 1, created_at: datetime = None, 
                 updated_at: datetime = None):
        self.id = id
        self.username = username
        self.email = email
        self.phone = phone
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """从字典创建用户对象"""
        return cls(
            id=data.get('id'),
            username=data.get('username'),
            email=data.get('email'),
            phone=data.get('phone'),
            status=data.get('status', 1),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def is_active(self) -> bool:
        """检查用户是否激活"""
        return self.status == 1
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', status={self.status})>"