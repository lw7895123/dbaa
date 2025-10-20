"""
Redis客户端管理模块
提供Redis连接池和缓存操作
"""
import json
import logging
import threading
from typing import Optional, Dict, List, Any, Union
import redis
from redis.connection import ConnectionPool
from .config import config

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.pool = None
            self.client = None
            self.initialized = True
            # 延迟初始化Redis客户端，避免导入时立即连接
    
    def _init_client(self):
        """初始化Redis客户端"""
        try:
            redis_config = config.REDIS_CONFIG
            self.pool = ConnectionPool(
                host=redis_config['host'],
                port=redis_config['port'],
                password=redis_config['password'],
                db=redis_config['db'],
                decode_responses=redis_config['decode_responses'],
                socket_connect_timeout=redis_config['socket_connect_timeout'],
                socket_timeout=redis_config['socket_timeout'],
                retry_on_timeout=redis_config['retry_on_timeout'],
                health_check_interval=redis_config['health_check_interval'],
                max_connections=redis_config['max_connections']
            )
            self.client = redis.Redis(connection_pool=self.pool)
            # 测试连接
            self.client.ping()
            logger.info("Redis连接初始化成功")
        except Exception as e:
            logger.error(f"Redis连接初始化失败: {e}")
            raise
    
    def get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        # 延迟初始化Redis客户端
        if self.client is None:
            self._init_client()
        return self.client
    
    def set(self, key: str, value: Union[str, Dict, List], ex: Optional[int] = None) -> bool:
        """设置键值"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis设置键值失败 {key}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取键值"""
        try:
            value = self.client.get(key)
            if value is None:
                return default
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis获取键值失败 {key}: {e}")
            return default
    
    def delete(self, *keys: str) -> int:
        """删除键"""
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis删除键失败 {keys}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis检查键存在失败 {key}: {e}")
            return False
    
    def expire(self, key: str, time: int) -> bool:
        """设置键过期时间"""
        try:
            return self.client.expire(key, time)
        except Exception as e:
            logger.error(f"Redis设置过期时间失败 {key}: {e}")
            return False
    
    def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """设置哈希表"""
        try:
            # 将字典值转换为JSON字符串
            json_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list)):
                    json_mapping[k] = json.dumps(v, ensure_ascii=False)
                else:
                    json_mapping[k] = str(v)
            return self.client.hset(name, mapping=json_mapping)
        except Exception as e:
            logger.error(f"Redis设置哈希表失败 {name}: {e}")
            return 0
    
    def hget(self, name: str, key: str, default: Any = None) -> Any:
        """获取哈希表字段值"""
        try:
            value = self.client.hget(name, key)
            if value is None:
                return default
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis获取哈希表字段失败 {name}.{key}: {e}")
            return default
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """获取哈希表所有字段"""
        try:
            data = self.client.hgetall(name)
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception as e:
            logger.error(f"Redis获取哈希表失败 {name}: {e}")
            return {}
    
    def lpush(self, name: str, *values: Any) -> int:
        """向列表左侧推入元素"""
        try:
            json_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    json_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    json_values.append(str(value))
            return self.client.lpush(name, *json_values)
        except Exception as e:
            logger.error(f"Redis列表推入失败 {name}: {e}")
            return 0
    
    def rpop(self, name: str, count: Optional[int] = None) -> Union[Any, List[Any], None]:
        """从列表右侧弹出元素"""
        try:
            if count is None:
                value = self.client.rpop(name)
                if value is None:
                    return None
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            else:
                values = self.client.rpop(name, count)
                result = []
                for value in values:
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        result.append(value)
                return result
        except Exception as e:
            logger.error(f"Redis列表弹出失败 {name}: {e}")
            return None if count is None else []
    
    def llen(self, name: str) -> int:
        """获取列表长度"""
        try:
            return self.client.llen(name)
        except Exception as e:
            logger.error(f"Redis获取列表长度失败 {name}: {e}")
            return 0
    
    def sadd(self, name: str, *values: Any) -> int:
        """向集合添加元素"""
        try:
            json_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    json_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    json_values.append(str(value))
            return self.client.sadd(name, *json_values)
        except Exception as e:
            logger.error(f"Redis集合添加失败 {name}: {e}")
            return 0
    
    def srem(self, name: str, *values: Any) -> int:
        """从集合移除元素"""
        try:
            json_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    json_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    json_values.append(str(value))
            return self.client.srem(name, *json_values)
        except Exception as e:
            logger.error(f"Redis集合移除失败 {name}: {e}")
            return 0
    
    def smembers(self, name: str) -> set:
        """获取集合所有成员"""
        try:
            members = self.client.smembers(name)
            result = set()
            for member in members:
                try:
                    result.add(json.loads(member))
                except (json.JSONDecodeError, TypeError):
                    result.add(member)
            return result
        except Exception as e:
            logger.error(f"Redis获取集合成员失败 {name}: {e}")
            return set()

    def close(self):
        """关闭Redis连接"""
        try:
            if self.client:
                self.client.close()
                self.client = None
            if self.pool:
                self.pool.disconnect()
                self.pool = None
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接时出错: {e}")


class CacheService:
    """缓存服务"""
    
    def __init__(self):
        self.redis = RedisManager()
    
    def set_user_status(self, user_id: int, status: int, ttl: int = 3600) -> bool:
        """设置用户状态缓存"""
        key = config.REDIS_KEYS['user_status'].format(user_id)
        return self.redis.set(key, status, ex=ttl)
    
    def get_user_status(self, user_id: int) -> Optional[int]:
        """获取用户状态缓存"""
        key = config.REDIS_KEYS['user_status'].format(user_id)
        return self.redis.get(key)
    
    def set_group_status(self, group_id: int, status: int, ttl: int = 3600) -> bool:
        """设置分组状态缓存"""
        key = config.REDIS_KEYS['group_status'].format(group_id)
        return self.redis.set(key, status, ex=ttl)
    
    def get_group_status(self, group_id: int) -> Optional[int]:
        """获取分组状态缓存"""
        key = config.REDIS_KEYS['group_status'].format(group_id)
        return self.redis.get(key)
    
    def push_order_to_queue(self, order_data: Dict[str, Any]) -> bool:
        """将订单推入处理队列"""
        key = config.REDIS_KEYS['order_queue']
        return self.redis.lpush(key, order_data) > 0
    
    def pop_order_from_queue(self, count: int = 1) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
        """从处理队列弹出订单"""
        key = config.REDIS_KEYS['order_queue']
        if count == 1:
            return self.redis.rpop(key)
        else:
            return self.redis.rpop(key, count)
    
    def get_queue_length(self) -> int:
        """获取队列长度"""
        key = config.REDIS_KEYS['order_queue']
        return self.redis.llen(key)
    
    def set_order_processing(self, order_id: int, worker_id: str, ttl: int = 300) -> bool:
        """标记订单正在处理"""
        key = config.REDIS_KEYS['order_processing'].format(order_id)
        return self.redis.set(key, worker_id, ex=ttl)
    
    def remove_order_processing(self, order_id: int) -> bool:
        """移除订单处理标记"""
        key = config.REDIS_KEYS['order_processing'].format(order_id)
        return self.redis.delete(key) > 0
    
    def is_order_processing(self, order_id: int) -> bool:
        """检查订单是否正在处理"""
        key = config.REDIS_KEYS['order_processing'].format(order_id)
        return self.redis.exists(key)
    
    def update_monitor_stats(self, stats: Dict[str, Any]) -> bool:
        """更新监控统计信息"""
        key = config.REDIS_KEYS['monitor_stats']
        return self.redis.hset(key, stats) > 0
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        key = config.REDIS_KEYS['monitor_stats']
        return self.redis.hgetall(key)
    
    def set_heartbeat(self, worker_id: str, ttl: int = 60) -> bool:
        """设置工作进程心跳"""
        key = config.REDIS_KEYS['heartbeat'].format(worker_id)
        return self.redis.set(key, {'timestamp': self.redis.client.time()[0]}, ex=ttl)
    
    def get_active_workers(self) -> List[str]:
        """获取活跃的工作进程"""
        pattern = config.REDIS_KEYS['heartbeat'].format('*')
        keys = self.redis.client.keys(pattern)
        return [key.split(':')[-1] for key in keys]


# 全局缓存服务实例
redis_manager = RedisManager()
cache_service = CacheService()