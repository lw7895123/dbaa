# -*- coding: utf-8 -*-
"""
Redis连接池管理器
提供高性能、高可靠性的Redis连接管理
"""
import threading
import time
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Union
import redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from ..config import REDIS_CONFIG, REDIS_KEYS, CACHE_CONFIG


class RedisManager:
    """Redis连接池管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.pool = None
        self.client = None
        self.config = REDIS_CONFIG.copy()
        self.logger = logging.getLogger(__name__)
        self._pool_initialized = False
    
    def initialize(self) -> bool:
        """初始化Redis连接池"""
        if self._pool_initialized:
            return True
        
        try:
            self._init_pool()
            self._pool_initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Redis连接池初始化失败: {e}")
            return False
    
    def _init_pool(self):
        """内部初始化Redis连接池方法"""
        self.pool = ConnectionPool(
            host=self.config['host'],
            port=self.config['port'],
            password=self.config['password'],
            db=self.config['db'],
            decode_responses=self.config['decode_responses'],
            socket_connect_timeout=self.config['socket_connect_timeout'],
            socket_timeout=self.config['socket_timeout'],
            retry_on_timeout=self.config['retry_on_timeout'],
            health_check_interval=self.config['health_check_interval'],
            **self.config['connection_pool_kwargs']
        )
        
        self.client = redis.Redis(connection_pool=self.pool)
        
        # 测试连接
        self.client.ping()
        self.logger.info(f"Redis连接池初始化成功，最大连接数: {self.config['connection_pool_kwargs']['max_connections']}")
    
    def _ensure_initialized(self):
        """确保连接池已初始化"""
        if not self._pool_initialized:
            if not self.initialize():
                raise RuntimeError("Redis连接池未初始化")
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=self._json_serializer)
        return str(value)
    
    def _json_serializer(self, obj):
        """JSON序列化器，处理datetime、Decimal等特殊类型"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    
    def _deserialize_value(self, value: str) -> Any:
        """反序列化值"""
        if not value:
            return None
        try:
            data = json.loads(value)
            return self._convert_datetime_strings(data)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _convert_datetime_strings(self, data):
        """递归转换数据中的datetime字符串"""
        if isinstance(data, dict):
            return {key: self._convert_datetime_strings(val) for key, val in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime_strings(item) for item in data]
        elif isinstance(data, str) and self._is_datetime_string(data):
            try:
                return datetime.fromisoformat(data)
            except ValueError:
                return data
        return data
    
    def _is_datetime_string(self, value: str) -> bool:
        """检查字符串是否为datetime格式"""
        if not isinstance(value, str) or len(value) < 19:
            return False
        # 检查是否符合ISO格式的datetime字符串
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False
    
    def set(self, key: str, value: Any, ex: Optional[int] = None, 
            px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        """设置键值"""
        try:
            self._ensure_initialized()
            serialized_value = self._serialize_value(value)
            return self.client.set(key, serialized_value, ex=ex, px=px, nx=nx, xx=xx)
        except RedisError as e:
            self.logger.error(f"Redis SET失败: key={key}, error={e}")
            return False
    
    def get(self, key: str) -> Any:
        """获取值"""
        try:
            self._ensure_initialized()
            value = self.client.get(key)
            return self._deserialize_value(value) if value else None
        except RedisError as e:
            self.logger.error(f"Redis GET失败: key={key}, error={e}")
            return None
    
    def delete(self, *keys: str) -> int:
        """删除键"""
        try:
            return self.client.delete(*keys)
        except RedisError as e:
            self.logger.error(f"Redis DELETE失败: keys={keys}, error={e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return bool(self.client.exists(key))
        except RedisError as e:
            self.logger.error(f"Redis EXISTS失败: key={key}, error={e}")
            return False
    
    def expire(self, key: str, time: int) -> bool:
        """设置过期时间"""
        try:
            return self.client.expire(key, time)
        except RedisError as e:
            self.logger.error(f"Redis EXPIRE失败: key={key}, error={e}")
            return False
    
    def ttl(self, key: str) -> int:
        """获取剩余生存时间"""
        try:
            return self.client.ttl(key)
        except RedisError as e:
            self.logger.error(f"Redis TTL失败: key={key}, error={e}")
            return -1
    
    def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """设置哈希表"""
        try:
            serialized_mapping = {k: self._serialize_value(v) for k, v in mapping.items()}
            return self.client.hset(name, mapping=serialized_mapping)
        except RedisError as e:
            self.logger.error(f"Redis HSET失败: name={name}, error={e}")
            return 0
    
    def hget(self, name: str, key: str) -> Any:
        """获取哈希表字段值"""
        try:
            value = self.client.hget(name, key)
            return self._deserialize_value(value) if value else None
        except RedisError as e:
            self.logger.error(f"Redis HGET失败: name={name}, key={key}, error={e}")
            return None
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """获取哈希表所有字段"""
        try:
            data = self.client.hgetall(name)
            return {k: self._deserialize_value(v) for k, v in data.items()} if data else {}
        except RedisError as e:
            self.logger.error(f"Redis HGETALL失败: name={name}, error={e}")
            return {}
    
    def hdel(self, name: str, *keys: str) -> int:
        """删除哈希表字段"""
        try:
            return self.client.hdel(name, *keys)
        except RedisError as e:
            self.logger.error(f"Redis HDEL失败: name={name}, keys={keys}, error={e}")
            return 0
    
    def sadd(self, name: str, *values: Any) -> int:
        """添加集合成员"""
        try:
            serialized_values = [self._serialize_value(v) for v in values]
            return self.client.sadd(name, *serialized_values)
        except RedisError as e:
            self.logger.error(f"Redis SADD失败: name={name}, error={e}")
            return 0
    
    def srem(self, name: str, *values: Any) -> int:
        """移除集合成员"""
        try:
            serialized_values = [self._serialize_value(v) for v in values]
            return self.client.srem(name, *serialized_values)
        except RedisError as e:
            self.logger.error(f"Redis SREM失败: name={name}, error={e}")
            return 0
    
    def smembers(self, name: str) -> set:
        """获取集合所有成员"""
        try:
            members = self.client.smembers(name)
            return {self._deserialize_value(m) for m in members} if members else set()
        except RedisError as e:
            self.logger.error(f"Redis SMEMBERS失败: name={name}, error={e}")
            return set()
    
    def sismember(self, name: str, value: Any) -> bool:
        """检查是否为集合成员"""
        try:
            serialized_value = self._serialize_value(value)
            return self.client.sismember(name, serialized_value)
        except RedisError as e:
            self.logger.error(f"Redis SISMEMBER失败: name={name}, error={e}")
            return False
    
    def lpush(self, name: str, *values: Any) -> int:
        """从左侧推入列表"""
        try:
            serialized_values = [self._serialize_value(v) for v in values]
            return self.client.lpush(name, *serialized_values)
        except RedisError as e:
            self.logger.error(f"Redis LPUSH失败: name={name}, error={e}")
            return 0
    
    def rpop(self, name: str) -> Any:
        """从右侧弹出列表元素"""
        try:
            value = self.client.rpop(name)
            return self._deserialize_value(value) if value else None
        except RedisError as e:
            self.logger.error(f"Redis RPOP失败: name={name}, error={e}")
            return None
    
    def llen(self, name: str) -> int:
        """获取列表长度"""
        try:
            return self.client.llen(name)
        except RedisError as e:
            self.logger.error(f"Redis LLEN失败: name={name}, error={e}")
            return 0
    
    # 业务相关的缓存方法
    def cache_user(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """缓存用户信息"""
        key = f"{REDIS_KEYS['user_prefix']}{user_id}"
        return self.set(key, user_data, ex=CACHE_CONFIG['user_cache_ttl'])
    
    def get_cached_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取缓存的用户信息"""
        key = f"{REDIS_KEYS['user_prefix']}{user_id}"
        return self.get(key)
    
    def cache_user_strategies(self, user_id: int, strategies: List[Dict[str, Any]]) -> bool:
        """缓存用户策略"""
        key = f"{REDIS_KEYS['strategy_prefix']}{user_id}"
        return self.set(key, strategies, ex=CACHE_CONFIG['strategy_cache_ttl'])
    
    def get_cached_user_strategies(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的用户策略"""
        key = f"{REDIS_KEYS['strategy_prefix']}{user_id}"
        return self.get(key)
    
    def cache_user_orders(self, user_id: int, orders: List[Dict[str, Any]]) -> bool:
        """缓存用户订单"""
        key = f"{REDIS_KEYS['user_orders_prefix']}{user_id}"
        return self.set(key, orders, ex=CACHE_CONFIG['order_cache_ttl'])
    
    def get_cached_user_orders(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的用户订单"""
        key = f"{REDIS_KEYS['user_orders_prefix']}{user_id}"
        return self.get(key)
    
    def add_active_user(self, user_id: int) -> bool:
        """添加活跃用户"""
        return bool(self.sadd(REDIS_KEYS['active_users'], user_id))
    
    def remove_active_user(self, user_id: int) -> bool:
        """移除活跃用户"""
        return bool(self.srem(REDIS_KEYS['active_users'], user_id))
    
    def get_active_users(self) -> set:
        """获取所有活跃用户"""
        return self.smembers(REDIS_KEYS['active_users'])
    
    def is_user_active(self, user_id: int) -> bool:
        """检查用户是否活跃"""
        return self.sismember(REDIS_KEYS['active_users'], user_id)
    
    def set_strategy_status(self, strategy_id: int, status: int) -> bool:
        """设置策略状态"""
        key = f"{REDIS_KEYS['strategy_status']}{strategy_id}"
        return self.set(key, status, ex=CACHE_CONFIG['strategy_cache_ttl'])
    
    def get_strategy_status(self, strategy_id: int) -> Optional[int]:
        """获取策略状态"""
        key = f"{REDIS_KEYS['strategy_status']}{strategy_id}"
        return self.get(key)
    
    def clear_user_cache(self, user_id: int):
        """清除用户相关缓存"""
        keys_to_delete = [
            f"{REDIS_KEYS['user_prefix']}{user_id}",
            f"{REDIS_KEYS['strategy_prefix']}{user_id}",
            f"{REDIS_KEYS['user_orders_prefix']}{user_id}"
        ]
        self.delete(*keys_to_delete)
        self.remove_active_user(user_id)
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        try:
            info = self.client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
        except RedisError as e:
            self.logger.error(f"获取Redis连接信息失败: {e}")
            return {}
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            return self.client.ping()
        except Exception as e:
            self.logger.error(f"Redis健康检查失败: {e}")
            return False
    
    def close_pool(self):
        """关闭连接池"""
        try:
            if self.pool:
                self.pool.disconnect()
                self.logger.info("Redis连接池已关闭")
        except Exception as e:
            self.logger.error(f"关闭Redis连接池失败: {e}")
    
    def close(self):
        """关闭Redis连接（close_pool的别名）"""
        self.close_pool()


# 全局Redis管理器实例
redis_manager = RedisManager()