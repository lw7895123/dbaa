"""
数据库连接池管理模块
提供MySQL连接池和基础数据库操作
"""
import logging
import threading
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
from .config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
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
            self.initialized = True
            # 延迟初始化连接池，避免导入时立即连接
    
    def _init_pool(self):
        """初始化连接池"""
        try:
            mysql_config = config.MYSQL_CONFIG
            self.pool = PooledDB(
                creator=pymysql,
                maxconnections=mysql_config['pool_size'] + mysql_config['max_overflow'],
                mincached=mysql_config['pool_size'] // 2,
                maxcached=mysql_config['pool_size'],
                maxshared=mysql_config['pool_size'],
                blocking=True,
                maxusage=None,
                setsession=[],
                ping=1,  # 使用ping检查连接
                host=mysql_config['host'],
                port=mysql_config['port'],
                user=mysql_config['user'],
                password=mysql_config['password'],
                database=mysql_config['database'],
                charset=mysql_config['charset'],
                autocommit=mysql_config['autocommit'],
                cursorclass=DictCursor
            )
            logger.info("数据库连接池初始化成功")
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        # 延迟初始化连接池
        if self.pool is None:
            self._init_pool()
            
        connection = None
        try:
            connection = self.pool.connection()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"数据库操作错误: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行查询SQL"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                return cursor.fetchall()
            finally:
                cursor.close()
    
    def execute_update(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行更新SQL，返回影响行数"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                affected_rows = cursor.execute(sql, params)
                conn.commit()
                return affected_rows
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def execute_batch(self, sql: str, params_list: List[Tuple]) -> int:
        """批量执行SQL"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                affected_rows = cursor.executemany(sql, params_list)
                conn.commit()
                return affected_rows
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def get_last_insert_id(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行插入SQL并返回最后插入的ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                last_id = cursor.lastrowid
                conn.commit()
                return last_id
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    def close_all(self):
        """关闭数据库连接池"""
        try:
            if self.pool:
                # PooledDB没有直接的close方法，但我们可以设置为None让垃圾回收处理
                self.pool = None
                logger.info("数据库连接池已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接池时出错: {e}")


class UserDAO:
    """用户数据访问对象"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        sql = "SELECT * FROM users WHERE id = %s"
        result = self.db.execute_query(sql, (user_id,))
        return result[0] if result else None
    
    def get_active_users(self) -> List[Dict[str, Any]]:
        """获取所有活跃用户"""
        sql = "SELECT * FROM users WHERE status = %s ORDER BY id"
        return self.db.execute_query(sql, (config.USER_STATUS['ENABLED'],))
    
    def update_user_status(self, user_id: int, status: int) -> bool:
        """更新用户状态"""
        sql = "UPDATE users SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        affected_rows = self.db.execute_update(sql, (status, user_id))
        return affected_rows > 0


class OrderGroupDAO:
    """订单分组数据访问对象"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取订单分组"""
        sql = "SELECT * FROM order_groups WHERE id = %s"
        result = self.db.execute_query(sql, (group_id,))
        return result[0] if result else None
    
    def get_user_active_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的活跃分组"""
        sql = """
        SELECT og.* FROM order_groups og 
        JOIN users u ON og.user_id = u.id 
        WHERE og.user_id = %s AND og.status = %s AND u.status = %s
        ORDER BY og.id
        """
        return self.db.execute_query(sql, (
            user_id, 
            config.GROUP_STATUS['OPEN'], 
            config.USER_STATUS['ENABLED']
        ))
    
    def get_all_active_groups(self) -> List[Dict[str, Any]]:
        """获取所有活跃分组"""
        sql = """
        SELECT og.* FROM order_groups og 
        JOIN users u ON og.user_id = u.id 
        WHERE og.status = %s AND u.status = %s
        ORDER BY og.user_id, og.id
        """
        return self.db.execute_query(sql, (
            config.GROUP_STATUS['OPEN'], 
            config.USER_STATUS['ENABLED']
        ))
    
    def update_group_status(self, group_id: int, status: int) -> bool:
        """更新分组状态"""
        sql = "UPDATE order_groups SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        affected_rows = self.db.execute_update(sql, (status, group_id))
        return affected_rows > 0


class OrderDAO:
    """订单数据访问对象"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取订单"""
        sql = "SELECT * FROM orders WHERE id = %s"
        result = self.db.execute_query(sql, (order_id,))
        return result[0] if result else None
    
    def get_pending_orders(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取待处理订单"""
        sql = """
        SELECT o.* FROM orders o
        JOIN order_groups og ON o.group_id = og.id
        JOIN users u ON o.user_id = u.id
        WHERE o.status IN (%s, %s) 
        AND og.status = %s 
        AND u.status = %s
        ORDER BY o.priority DESC, o.created_at ASC
        LIMIT %s
        """
        return self.db.execute_query(sql, (
            config.ORDER_STATUS['PENDING'],
            config.ORDER_STATUS['PARTIAL'],
            config.GROUP_STATUS['OPEN'],
            config.USER_STATUS['ENABLED'],
            limit
        ))
    
    def get_user_orders(self, user_id: int, status: Optional[Any] = None) -> List[Dict[str, Any]]:
        """获取用户订单"""
        if status:
            if isinstance(status, list):
                # 支持状态列表
                placeholders = ','.join(['%s'] * len(status))
                sql = f"SELECT * FROM orders WHERE user_id = %s AND status IN ({placeholders}) ORDER BY priority DESC, created_at ASC"
                return self.db.execute_query(sql, (user_id, *status))
            else:
                # 单个状态
                sql = "SELECT * FROM orders WHERE user_id = %s AND status = %s ORDER BY priority DESC, created_at ASC"
                return self.db.execute_query(sql, (user_id, status))
        else:
            sql = "SELECT * FROM orders WHERE user_id = %s ORDER BY priority DESC, created_at ASC"
            return self.db.execute_query(sql, (user_id,))
    
    def get_group_orders(self, group_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取分组订单"""
        if status:
            sql = "SELECT * FROM orders WHERE group_id = %s AND status = %s ORDER BY created_at DESC"
            return self.db.execute_query(sql, (group_id, status))
        else:
            sql = "SELECT * FROM orders WHERE group_id = %s ORDER BY created_at DESC"
            return self.db.execute_query(sql, (group_id,))
    
    def update_order_status(self, order_id: int, status: str, filled_quantity: Optional[float] = None) -> bool:
        """更新订单状态"""
        if filled_quantity is not None:
            sql = """
            UPDATE orders 
            SET status = %s, filled_quantity = %s, updated_at = CURRENT_TIMESTAMP,
                filled_at = CASE WHEN %s IN (%s, %s) THEN CURRENT_TIMESTAMP ELSE filled_at END
            WHERE id = %s
            """
            affected_rows = self.db.execute_update(sql, (
                status, filled_quantity, status,
                config.ORDER_STATUS['FILLED'], config.ORDER_STATUS['PARTIAL'],
                order_id
            ))
        else:
            sql = """
            UPDATE orders 
            SET status = %s, updated_at = CURRENT_TIMESTAMP,
                filled_at = CASE WHEN %s IN (%s, %s) THEN CURRENT_TIMESTAMP ELSE filled_at END
            WHERE id = %s
            """
            affected_rows = self.db.execute_update(sql, (
                status, status,
                config.ORDER_STATUS['FILLED'], config.ORDER_STATUS['PARTIAL'],
                order_id
            ))
        return affected_rows > 0
    
    def create_order(self, order_data: Dict[str, Any]) -> int:
        """创建订单"""
        sql = """
        INSERT INTO orders (user_id, group_id, order_no, order_type, symbol, 
                           price, quantity, status, priority)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.get_last_insert_id(sql, (
            order_data['user_id'],
            order_data['group_id'],
            order_data['order_no'],
            order_data['order_type'],
            order_data['symbol'],
            order_data['price'],
            order_data['quantity'],
            order_data.get('status', config.ORDER_STATUS['PENDING']),
            order_data.get('priority', 0)
        ))
    
    def log_status_change(self, order_id: int, old_status: str, new_status: str, 
                         old_filled: float, new_filled: float, reason: str = None) -> int:
        """记录状态变更日志"""
        sql = """
        INSERT INTO order_status_logs (order_id, old_status, new_status, 
                                     old_filled_quantity, new_filled_quantity, change_reason)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self.db.get_last_insert_id(sql, (
            order_id, old_status, new_status, old_filled, new_filled, reason
        ))


# 全局数据访问对象实例
db_manager = DatabaseManager()
user_dao = UserDAO()
order_group_dao = OrderGroupDAO()
order_dao = OrderDAO()