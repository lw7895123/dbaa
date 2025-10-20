"""
用户级别的订单管理器
解决多用户并发处理中的数据隔离和公平性问题
"""
import threading
import time
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict, deque
import random

from .config import config
from .database import order_dao, user_dao, order_group_dao
from .redis_client import cache_service
from .logger import get_system_logger, log_order_event, log_order_status_change


@dataclass
class UserOrderBatch:
    """用户订单批次"""
    user_id: int
    orders: List[Dict[str, Any]]
    priority_score: float
    last_processed: datetime
    processing_count: int = 0


class UserOrderQueue:
    """用户订单队列管理器"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.pending_orders: deque = deque()
        self.processing_orders: Set[int] = set()
        self.last_fetch_time = 0
        self.fetch_interval = 5.0  # 5秒刷新一次用户订单
        self.max_concurrent = 3  # 每个用户最多同时处理3个订单
        self.lock = threading.Lock()
    
    def need_refresh(self) -> bool:
        """检查是否需要刷新订单"""
        return time.time() - self.last_fetch_time > self.fetch_interval
    
    def refresh_orders(self) -> int:
        """刷新用户的待处理订单"""
        with self.lock:
            try:
                # 获取用户的待处理订单
                user_orders = order_dao.get_user_orders(
                    self.user_id, 
                    status=[config.ORDER_STATUS['PENDING'], config.ORDER_STATUS['PARTIAL']]
                )
                
                # 过滤掉正在处理的订单
                new_orders = [
                    order for order in user_orders 
                    if order['id'] not in self.processing_orders
                ]
                
                # 按优先级和创建时间排序
                new_orders.sort(key=lambda x: (-x.get('priority', 0), x['created_at']))
                
                # 更新队列
                self.pending_orders.clear()
                self.pending_orders.extend(new_orders)
                self.last_fetch_time = time.time()
                
                return len(new_orders)
                
            except Exception as e:
                get_system_logger().error(f"刷新用户{self.user_id}订单失败: {e}")
                return 0
    
    def get_next_order(self) -> Optional[Dict[str, Any]]:
        """获取下一个待处理订单"""
        with self.lock:
            # 检查并发限制
            if len(self.processing_orders) >= self.max_concurrent:
                return None
            
            # 获取下一个订单
            if self.pending_orders:
                order = self.pending_orders.popleft()
                self.processing_orders.add(order['id'])
                return order
            
            return None
    
    def mark_order_completed(self, order_id: int):
        """标记订单处理完成"""
        with self.lock:
            self.processing_orders.discard(order_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        with self.lock:
            return {
                'user_id': self.user_id,
                'pending_count': len(self.pending_orders),
                'processing_count': len(self.processing_orders),
                'last_fetch_time': self.last_fetch_time
            }


class UserOrderManager:
    """用户订单管理器"""
    
    def __init__(self):
        self.logger = get_system_logger()
        self.user_queues: Dict[int, UserOrderQueue] = {}
        self.active_users: Set[int] = set()
        self.user_priority_scores: Dict[int, float] = defaultdict(float)
        self.lock = threading.Lock()
        self.last_user_refresh = 0
        self.user_refresh_interval = 30.0  # 30秒刷新一次活跃用户列表
    
    def refresh_active_users(self) -> int:
        """刷新活跃用户列表"""
        try:
            current_time = time.time()
            if current_time - self.last_user_refresh < self.user_refresh_interval:
                return len(self.active_users)
            
            # 获取有待处理订单的活跃用户
            active_users_query = """
            SELECT DISTINCT o.user_id, u.status, COUNT(o.id) as order_count,
                   AVG(o.priority) as avg_priority
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN order_groups og ON o.group_id = og.id
            WHERE o.status IN (%s, %s) 
            AND u.status = %s 
            AND og.status = %s
            GROUP BY o.user_id, u.status
            ORDER BY order_count DESC, avg_priority DESC
            """
            
            from .database import db_manager
            active_users_data = db_manager.execute_query(active_users_query, (
                config.ORDER_STATUS['PENDING'],
                config.ORDER_STATUS['PARTIAL'],
                config.USER_STATUS['ENABLED'],
                config.GROUP_STATUS['OPEN']
            ))
            
            with self.lock:
                # 更新活跃用户集合
                new_active_users = set()
                for user_data in active_users_data:
                    user_id = user_data['user_id']
                    new_active_users.add(user_id)
                    
                    # 计算用户优先级分数（订单数量 + 平均优先级）
                    order_count = user_data['order_count']
                    avg_priority = user_data.get('avg_priority', 0) or 0
                    self.user_priority_scores[user_id] = order_count * 0.7 + avg_priority * 0.3
                
                # 移除不活跃的用户队列
                inactive_users = self.active_users - new_active_users
                for user_id in inactive_users:
                    if user_id in self.user_queues:
                        del self.user_queues[user_id]
                
                self.active_users = new_active_users
                self.last_user_refresh = current_time
            
            self.logger.info(f"刷新活跃用户列表: {len(self.active_users)}个用户")
            return len(self.active_users)
            
        except Exception as e:
            self.logger.error(f"刷新活跃用户失败: {e}")
            return 0
    
    def get_user_queue(self, user_id: int) -> UserOrderQueue:
        """获取用户订单队列"""
        with self.lock:
            if user_id not in self.user_queues:
                self.user_queues[user_id] = UserOrderQueue(user_id)
            return self.user_queues[user_id]
    
    def get_next_user_order(self) -> Optional[Dict[str, Any]]:
        """获取下一个用户订单（轮询方式）"""
        try:
            # 刷新活跃用户列表
            self.refresh_active_users()
            
            if not self.active_users:
                return None
            
            # 按优先级分数排序用户
            sorted_users = sorted(
                self.active_users, 
                key=lambda uid: self.user_priority_scores.get(uid, 0),
                reverse=True
            )
            
            # 轮询用户获取订单
            for user_id in sorted_users:
                user_queue = self.get_user_queue(user_id)
                
                # 检查是否需要刷新用户订单
                if user_queue.need_refresh():
                    refresh_count = user_queue.refresh_orders()
                    if refresh_count > 0:
                        self.logger.debug(f"用户{user_id}刷新了{refresh_count}个订单")
                
                # 获取用户的下一个订单
                order = user_queue.get_next_order()
                if order:
                    self.logger.debug(f"分配订单{order['id']}给用户{user_id}")
                    return order
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取下一个用户订单失败: {e}")
            return None
    
    def mark_order_completed(self, order_id: int, user_id: int):
        """标记订单处理完成"""
        try:
            if user_id in self.user_queues:
                self.user_queues[user_id].mark_order_completed(order_id)
        except Exception as e:
            self.logger.error(f"标记订单{order_id}完成失败: {e}")
    
    def get_active_users(self) -> List[int]:
        """获取活跃用户列表"""
        with self.lock:
            return list(self.active_users)
    
    def get_next_user_orders(self, worker_id: str, batch_size: int = 10) -> Tuple[Optional[int], List[Dict[str, Any]]]:
        """获取下一个用户的订单批次"""
        try:
            # 尝试获取用户锁并获取订单
            for user_id in self.active_users:
                if self._try_acquire_user_lock(user_id, worker_id):
                    try:
                        # 获取用户队列
                        queue = self.get_user_queue(user_id)
                        
                        # 刷新订单（如果需要）
                        if queue.need_refresh():
                            queue.refresh_orders()
                        
                        # 获取订单批次
                        orders = []
                        for _ in range(batch_size):
                            order = queue.get_next_order()
                            if order:
                                orders.append(order)
                            else:
                                break
                        
                        if orders:
                            self.logger.debug(f"为工作进程 {worker_id} 分配用户 {user_id} 的 {len(orders)} 个订单")
                            return user_id, orders
                        else:
                            # 没有订单，释放锁
                            self.release_user_lock(user_id, worker_id)
                    except Exception as e:
                        self.logger.error(f"获取用户 {user_id} 订单时出错: {e}")
                        self.release_user_lock(user_id, worker_id)
            
            return None, []
            
        except Exception as e:
            self.logger.error(f"获取下一个用户订单时出错: {e}")
            return None, []
    
    def _try_acquire_user_lock(self, user_id: int, worker_id: str) -> bool:
        """尝试获取用户锁"""
        try:
            lock_key = config.REDIS_KEYS['user_lock'].format(user_id)
            timeout = config.USER_ORDER_CONFIG['user_lock_timeout']
            
            # 使用Redis SET命令实现分布式锁
            result = cache_service.redis_client.set(
                lock_key, 
                worker_id, 
                nx=True,  # 只在键不存在时设置
                ex=timeout  # 设置过期时间
            )
            
            return result is True
            
        except Exception as e:
            self.logger.error(f"获取用户 {user_id} 锁时出错: {e}")
            return False
    
    def release_user_lock(self, user_id: int, worker_id: str):
        """释放用户锁"""
        try:
            lock_key = config.REDIS_KEYS['user_lock'].format(user_id)
            
            # 使用Lua脚本确保只有锁的持有者才能释放锁
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = cache_service.redis_client.eval(lua_script, 1, lock_key, worker_id)
            
            if result == 1:
                self.logger.debug(f"工作进程 {worker_id} 成功释放用户 {user_id} 的锁")
            else:
                self.logger.warning(f"工作进程 {worker_id} 无法释放用户 {user_id} 的锁（可能已过期或被其他进程持有）")
                
        except Exception as e:
            self.logger.error(f"释放用户 {user_id} 锁时出错: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self.lock:
            total_pending = 0
            total_processing = 0
            user_statuses = []
            
            for user_id, queue in self.user_queues.items():
                status = queue.get_queue_status()
                user_statuses.append(status)
                total_pending += status['pending_count']
                total_processing += status['processing_count']
            
            return {
                'active_users': len(self.active_users),
                'total_pending_orders': total_pending,
                'total_processing_orders': total_processing,
                'user_queues': len(self.user_queues),
                'user_statuses': user_statuses
            }


# 全局用户订单管理器实例
user_order_manager = UserOrderManager()