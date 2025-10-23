# -*- coding: utf-8 -*-
"""
系统核心配置文件
包含数据库连接、Redis配置、日志配置等
"""
import os
from datetime import timedelta

# 基础配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# MySQL数据库配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456789',
    'database': 'strategy',
    'charset': 'utf8mb4',
    'autocommit': True,
    # 连接池配置
    'pool_name': 'strategy_pool',
    'pool_size': 20,
    'pool_reset_session': True,
    'pool_pre_ping': True,
    'max_overflow': 30,
    'pool_recycle': 3600,  # 1小时回收连接
    'pool_timeout': 30,
}

# Redis配置
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'password': 123456789,
    'db': 0,
    'decode_responses': True,
    'socket_connect_timeout': 5,
    'socket_timeout': 5,
    'retry_on_timeout': True,
    'health_check_interval': 30,
    # 连接池配置
    'connection_pool_kwargs': {
        'max_connections': 50,
        'socket_keepalive': True,
        'socket_keepalive_options': {},
    }
}

# 监控配置
MONITOR_CONFIG = {
    'max_workers': 100,  # 最大工作线程数
    'check_interval': 0.1,  # 订单检查间隔(秒)
    'batch_size': 100,  # 批量处理大小
    'queue_maxsize': 1000,  # 队列最大大小
    'strategy_check_interval': 5,  # 策略状态检查间隔(秒)
    'user_cleanup_interval': 60,  # 用户清理检查间隔(秒)
}

# 日志配置
LOG_CONFIG = {
    'log_dir': os.path.join(PROJECT_ROOT, 'logs', 'users'),
    'log_level': 'INFO',
    'log_format': '%(asctime)s - %(pathname)s:%(lineno)d - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
    'retention_days': 7,  # 保留7天
    'cleanup_interval': 3600,  # 清理检查间隔(秒)
}

# 缓存配置
CACHE_CONFIG = {
    'user_cache_ttl': 300,  # 用户信息缓存5分钟
    'strategy_cache_ttl': 60,  # 策略信息缓存1分钟
    'order_cache_ttl': 30,  # 订单信息缓存30秒
    'batch_cache_size': 1000,  # 批量缓存大小
}

# 数据库表名
TABLE_NAMES = {
    'users': 'users',
    'orders': 'orders',
    'strategies': 'user_strategies',
}

# Redis键前缀
REDIS_KEYS = {
    'user_prefix': 'user:',
    'order_prefix': 'order:',
    'strategy_prefix': 'strategy:',
    'user_orders_prefix': 'user_orders:',
    'active_users': 'active_users',
    'strategy_status': 'strategy_status:',
}

# 系统状态
SYSTEM_STATUS = {
    'startup_delay': 2,  # 启动延迟(秒)
    'graceful_shutdown_timeout': 30,  # 优雅关闭超时(秒)
    'health_check_interval': 10,  # 健康检查间隔(秒)
}