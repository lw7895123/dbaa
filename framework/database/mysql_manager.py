# -*- coding: utf-8 -*-
"""
MySQL连接池管理器
提供高性能、高可靠性的MySQL连接管理
"""
import threading
import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
import mysql.connector
from mysql.connector import pooling, Error
from ..config import MYSQL_CONFIG


class MySQLManager:
    """MySQL连接池管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MySQLManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.pool = None
        self.config = MYSQL_CONFIG.copy()
        self.logger = logging.getLogger(__name__)
        self._pool_initialized = False
    
    def initialize(self) -> bool:
        """初始化连接池"""
        if self._pool_initialized:
            return True
        
        try:
            self._init_pool()
            self._pool_initialized = True
            return True
        except Exception as e:
            self.logger.error(f"MySQL连接池初始化失败: {e}")
            return False
    
    def _init_pool(self):
        """内部初始化连接池方法"""
        self.pool = pooling.MySQLConnectionPool(
            pool_name=self.config['pool_name'],
            pool_size=self.config['pool_size'],
            pool_reset_session=self.config['pool_reset_session'],
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            charset=self.config['charset'],
            autocommit=self.config['autocommit'],
            use_unicode=True,
            sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO',
            time_zone='+08:00'
        )
        self.logger.info(f"MySQL连接池初始化成功，池大小: {self.config['pool_size']}")
    
    def _ensure_initialized(self):
        """确保连接池已初始化"""
        if not self._pool_initialized:
            if not self.initialize():
                raise RuntimeError("MySQL连接池未初始化")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        self._ensure_initialized()
        connection = None
        try:
            connection = self.pool.get_connection()
            if connection.is_connected():
                yield connection
            else:
                raise Error("连接已断开")
        except Error as e:
            self.logger.error(f"获取MySQL连接失败: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, 
                     fetch_one: bool = False, fetch_all: bool = True) -> Optional[Any]:
        """执行查询语句"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, params or ())
                
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                else:
                    result = None
                
                cursor.close()
                return result
        except Error as e:
            self.logger.error(f"执行查询失败: {query}, 参数: {params}, 错误: {e}")
            raise
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行更新语句（INSERT, UPDATE, DELETE）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                affected_rows = cursor.rowcount
                conn.commit()
                cursor.close()
                return affected_rows
        except Error as e:
            self.logger.error(f"执行更新失败: {query}, 参数: {params}, 错误: {e}")
            raise
    
    def execute_batch(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行语句"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                affected_rows = cursor.rowcount
                conn.commit()
                cursor.close()
                return affected_rows
        except Error as e:
            self.logger.error(f"批量执行失败: {query}, 错误: {e}")
            raise
    
    def execute_transaction(self, operations: List[Dict[str, Any]]) -> bool:
        """执行事务"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                conn.start_transaction()
                
                try:
                    for operation in operations:
                        query = operation['query']
                        params = operation.get('params', ())
                        cursor.execute(query, params)
                    
                    conn.commit()
                    cursor.close()
                    return True
                except Error as e:
                    conn.rollback()
                    cursor.close()
                    self.logger.error(f"事务执行失败，已回滚: {e}")
                    raise
        except Error as e:
            self.logger.error(f"事务执行失败: {e}")
            raise
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户信息"""
        query = "SELECT * FROM users WHERE id = %s AND status = 1"
        return self.execute_query(query, (user_id,), fetch_one=True)
    
    def get_user_strategies(self, user_id: int, status: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取用户策略列表"""
        if status is not None:
            query = "SELECT * FROM user_strategies WHERE user_id = %s AND status = %s ORDER BY created_at DESC"
            params = (user_id, status)
        else:
            query = "SELECT * FROM user_strategies WHERE user_id = %s ORDER BY created_at DESC"
            params = (user_id,)
        
        return self.execute_query(query, params, fetch_all=True) or []
    
    def get_users_with_active_strategies(self) -> List[Dict[str, Any]]:
        """获取有活跃策略的用户列表"""
        query = """
        SELECT DISTINCT u.id, u.username, u.email, u.status, u.created_at, u.updated_at
        FROM users u
        INNER JOIN user_strategies us ON u.id = us.user_id
        WHERE u.status = 1 AND us.status = 1
        ORDER BY u.id
        """
        return self.execute_query(query, fetch_all=True) or []
    
    def get_user_orders(self, user_id: int, strategy_id: Optional[int] = None, 
                       status: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取用户订单列表"""
        conditions = ["user_id = %s"]
        params = [user_id]
        
        if strategy_id is not None:
            conditions.append("strategy_id = %s")
            params.append(strategy_id)
        
        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        
        query = f"""
        SELECT * FROM orders 
        WHERE {' AND '.join(conditions)} 
        ORDER BY order_time DESC 
        LIMIT %s
        """
        params.append(limit)
        
        return self.execute_query(query, tuple(params), fetch_all=True) or []
    
    def get_active_orders(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取活跃订单（待处理和部分成交）"""
        if user_id:
            query = """
            SELECT * FROM orders 
            WHERE user_id = %s AND status IN (0, 1) 
            ORDER BY order_time ASC
            """
            params = (user_id,)
        else:
            query = """
            SELECT * FROM orders 
            WHERE status IN (0, 1) 
            ORDER BY order_time ASC
            """
            params = ()
        
        return self.execute_query(query, params, fetch_all=True) or []
    
    def update_order_status(self, order_id: int, status: int, 
                           filled_quantity: Optional[float] = None,
                           avg_price: Optional[float] = None,
                           commission: Optional[float] = None) -> bool:
        """更新订单状态"""
        update_fields = ["status = %s", "update_time = NOW()"]
        params = [status]
        
        if filled_quantity is not None:
            update_fields.append("filled_quantity = %s")
            params.append(filled_quantity)
        
        if avg_price is not None:
            update_fields.append("avg_price = %s")
            params.append(avg_price)
        
        if commission is not None:
            update_fields.append("commission = %s")
            params.append(commission)
        
        params.append(order_id)
        
        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id = %s"
        affected_rows = self.execute_update(query, tuple(params))
        return affected_rows > 0
    
    def update_strategy_status(self, strategy_id: int, status: int) -> bool:
        """更新策略状态"""
        query = "UPDATE user_strategies SET status = %s, updated_at = NOW() WHERE id = %s"
        affected_rows = self.execute_update(query, (status, strategy_id))
        return affected_rows > 0
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self.pool:
            return {"status": "未初始化"}
        
        try:
            return {
                "pool_name": self.pool.pool_name,
                "pool_size": self.pool.pool_size,
                "status": "正常"
            }
        except Exception as e:
            return {"status": f"异常: {e}"}
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result is not None
        except Exception as e:
            self.logger.error(f"MySQL健康检查失败: {e}")
            return False
    
    def close_pool(self):
        """关闭连接池"""
        if self.pool:
            try:
                # MySQL Connector/Python的连接池没有直接的关闭方法
                # 连接会在程序结束时自动关闭
                self.logger.info("MySQL连接池已标记为关闭")
            except Exception as e:
                self.logger.error(f"关闭MySQL连接池失败: {e}")
    
    def close(self):
        """关闭MySQL连接（close_pool的别名）"""
        self.close_pool()


# 全局MySQL管理器实例
mysql_manager = MySQLManager()