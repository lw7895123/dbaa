"""
项目配置文件
包含数据库连接、Redis连接、日志配置等
"""
import os
from typing import Dict, Any

class Config:
    """项目配置类"""
    
    # 环境配置
    ENV = 'development'
    DEBUG = False
    
    # 监控引擎配置
    MONITOR_WORKER_COUNT = int(os.getenv('MONITOR_WORKER_COUNT', 4))
    MONITOR_BATCH_SIZE = int(os.getenv('MONITOR_BATCH_SIZE', 100))
    
    # 数据库配置
    MYSQL_CONFIG = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '123456789'),
        'database': os.getenv('MYSQL_DATABASE', 'order_monitor'),
        'charset': 'utf8mb4',
        'autocommit': True,
        # 连接池配置
        'pool_name': 'order_monitor_pool',
        'pool_size': int(os.getenv('MYSQL_POOL_SIZE', 20)),
        'pool_reset_session': True,
        'pool_pre_ping': True,
        'max_overflow': int(os.getenv('MYSQL_MAX_OVERFLOW', 30)),
        'pool_recycle': 3600,  # 1小时回收连接
    }
    
    # Redis配置
    REDIS_CONFIG = {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'password': os.getenv('REDIS_PASSWORD', None),
        'db': int(os.getenv('REDIS_DB', 0)),
        'decode_responses': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'retry_on_timeout': True,
        'health_check_interval': 30,
        # 连接池配置
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', 50)),
    }
    
    # 监控配置
    MONITOR_CONFIG = {
        'check_interval': float(os.getenv('MONITOR_CHECK_INTERVAL', 0.1)),  # 检查间隔（秒）
        'batch_size': int(os.getenv('MONITOR_BATCH_SIZE', 100)),  # 批处理大小
        'max_workers': int(os.getenv('MONITOR_MAX_WORKERS', 10)),  # 最大工作进程数
        'queue_size': int(os.getenv('MONITOR_QUEUE_SIZE', 1000)),  # 队列大小
        'timeout': int(os.getenv('MONITOR_TIMEOUT', 30)),  # 超时时间（秒）
    }
    
    # 日志配置
    LOG_CONFIG = {
        'level': os.getenv('LOG_LEVEL', 'INFO'),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'date_format': '%Y-%m-%d %H:%M:%S',
        'log_dir': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs'),
        'max_file_size': 100 * 1024 * 1024,  # 100MB
        'backup_count': 5,
        'retention_days': 7,  # 保留7天
    }
    
    # Redis键配置
    REDIS_KEYS = {
        'user_status': 'user:status:{}',
        'group_status': 'group:status:{}',
        'order_queue': 'order:queue',
        'order_processing': 'order:processing:{}',
        'monitor_stats': 'monitor:stats',
        'heartbeat': 'monitor:heartbeat:{}',
        'user_queue': 'user:queue:{}',
        'user_lock': 'user:lock:{}',
        'user_last_processed': 'user:last_processed:{}',
        'active_users': 'users:active',
    }
    
    # 用户订单管理配置
    USER_ORDER_CONFIG = {
        'user_lock_timeout': int(os.getenv('USER_LOCK_TIMEOUT', 300)),  # 用户锁超时时间（秒）
        'user_queue_max_size': int(os.getenv('USER_QUEUE_MAX_SIZE', 1000)),  # 用户队列最大大小
        'round_robin_reset_interval': int(os.getenv('ROUND_ROBIN_RESET_INTERVAL', 3600)),  # 轮询重置间隔（秒）
        'user_batch_size': int(os.getenv('USER_BATCH_SIZE', 50)),  # 每个用户的批处理大小
        'max_retry_attempts': int(os.getenv('MAX_RETRY_ATTEMPTS', 3)),  # 最大重试次数
    }
    
    # 订单状态
    ORDER_STATUS = {
        'PENDING': 'PENDING',
        'PARTIAL': 'PARTIAL', 
        'FILLED': 'FILLED',
        'CANCELLED': 'CANCELLED',
    }
    
    # 用户状态
    USER_STATUS = {
        'DISABLED': 0,
        'ENABLED': 1,
    }
    
    # 分组状态
    GROUP_STATUS = {
        'CLOSED': 0,
        'OPEN': 1,
    }
    
    @classmethod
    def get_mysql_url(cls) -> str:
        """获取MySQL连接URL"""
        config = cls.MYSQL_CONFIG
        return f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}?charset={config['charset']}"
    
    @classmethod
    def get_log_file_path(cls, user_id: int) -> str:
        """获取用户日志文件路径"""
        log_dir = cls.LOG_CONFIG['log_dir']
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f'user_{user_id}.log')
    
    @classmethod
    def get_system_log_path(cls) -> str:
        """获取系统日志文件路径"""
        log_dir = cls.LOG_CONFIG['log_dir']
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, 'system.log')


# 开发环境配置
class DevelopmentConfig(Config):
    """开发环境配置"""
    ENV = 'development'
    DEBUG = True
    MYSQL_CONFIG = Config.MYSQL_CONFIG.copy()
    MYSQL_CONFIG.update({
        'pool_size': 5,
        'max_overflow': 10,
    })
    
    MONITOR_CONFIG = Config.MONITOR_CONFIG.copy()
    MONITOR_CONFIG.update({
        'check_interval': 1.0,  # 开发环境检查间隔更长
        'max_workers': 2,
    })


# 生产环境配置
class ProductionConfig(Config):
    """生产环境配置"""
    ENV = 'production'
    DEBUG = False
    MYSQL_CONFIG = Config.MYSQL_CONFIG.copy()
    MYSQL_CONFIG.update({
        'pool_size': 50,
        'max_overflow': 100,
    })
    
    REDIS_CONFIG = Config.REDIS_CONFIG.copy()
    REDIS_CONFIG.update({
        'max_connections': 200,
    })
    
    MONITOR_CONFIG = Config.MONITOR_CONFIG.copy()
    MONITOR_CONFIG.update({
        'check_interval': 0.05,  # 生产环境更频繁检查
        'max_workers': 20,
        'batch_size': 500,
    })


# 根据环境变量选择配置
def get_config() -> Config:
    """根据环境变量获取配置"""
    env = os.getenv('ENVIRONMENT', 'development').lower()
    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()


# 全局配置实例
config = get_config()