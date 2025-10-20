"""
订单监控核心引擎
支持高并发多进程处理和实时订单状态监控
"""
import asyncio
import multiprocessing
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import signal
import sys

from .config import config
from .database import order_dao, user_dao, order_group_dao
from .redis_client import cache_service
from .logger import get_system_logger, get_user_logger, log_order_event, log_order_status_change
from .user_order_manager import UserOrderManager


@dataclass
class OrderEvent:
    """订单事件数据类"""
    order_id: int
    user_id: int
    group_id: int
    event_type: str  # 'status_change', 'fill', 'cancel', 'create'
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    filled_quantity: Optional[float] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class OrderProcessor:
    """订单处理器"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.logger = None  # 延迟初始化，避免pickle问题
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0
    
    def _ensure_logger(self):
        """确保logger已初始化"""
        if self.logger is None:
            self.logger = get_system_logger()
    
    def process_order(self, order_data: Dict[str, Any]) -> bool:
        """处理单个订单"""
        try:
            order_id = order_data['id']
            user_id = order_data['user_id']
            
            # 检查订单是否已在处理中
            if cache_service.is_order_processing(order_id):
                return False
            
            # 标记订单正在处理
            cache_service.set_order_processing(order_id, self.worker_id)
            
            try:
                # 检查用户和分组状态
                if not self._check_order_eligibility(order_data):
                    return False
                
                # 模拟订单处理逻辑（实际项目中这里会是真实的交易逻辑）
                result = self._simulate_order_processing(order_data)
                
                if result:
                    self.processed_count += 1
                    log_order_event(user_id, order_id, "处理完成", f"工作进程: {self.worker_id}")
                
                return result
                
            finally:
                # 移除处理标记
                cache_service.remove_order_processing(order_id)
                
        except Exception as e:
            self.error_count += 1
            self._ensure_logger()
            self.logger.error(f"订单处理失败 {order_data.get('id', 'unknown')}: {e}")
            return False
    
    def _check_order_eligibility(self, order_data: Dict[str, Any]) -> bool:
        """检查订单是否符合处理条件"""
        user_id = order_data['user_id']
        group_id = order_data['group_id']
        
        # 检查用户状态
        user_status = cache_service.get_user_status(user_id)
        if user_status is None:
            # 从数据库获取用户状态并缓存
            user = user_dao.get_user_by_id(user_id)
            if not user or user['status'] != config.USER_STATUS['ENABLED']:
                return False
            cache_service.set_user_status(user_id, user['status'])
        elif user_status != config.USER_STATUS['ENABLED']:
            return False
        
        # 检查分组状态
        group_status = cache_service.get_group_status(group_id)
        if group_status is None:
            # 从数据库获取分组状态并缓存
            group = order_group_dao.get_group_by_id(group_id)
            if not group or group['status'] != config.GROUP_STATUS['OPEN']:
                return False
            cache_service.set_group_status(group_id, group['status'])
        elif group_status != config.GROUP_STATUS['OPEN']:
            return False
        
        return True
    
    def _simulate_order_processing(self, order_data: Dict[str, Any]) -> bool:
        """模拟订单处理（实际项目中替换为真实交易逻辑）"""
        order_id = order_data['id']
        current_status = order_data['status']
        
        # 模拟不同的处理结果
        import random
        
        if current_status == config.ORDER_STATUS['PENDING']:
            # 30% 概率完全成交，50% 概率部分成交，20% 概率保持待成交
            rand = random.random()
            if rand < 0.3:
                # 完全成交
                new_status = config.ORDER_STATUS['FILLED']
                filled_quantity = order_data['quantity']
            elif rand < 0.8:
                # 部分成交
                new_status = config.ORDER_STATUS['PARTIAL']
                filled_quantity = order_data['quantity'] * random.uniform(0.1, 0.9)
            else:
                # 保持待成交
                return True
        
        elif current_status == config.ORDER_STATUS['PARTIAL']:
            # 50% 概率完全成交，50% 概率继续部分成交
            rand = random.random()
            current_filled = order_data.get('filled_quantity', 0)
            remaining = order_data['quantity'] - current_filled
            
            if rand < 0.5:
                # 完全成交
                new_status = config.ORDER_STATUS['FILLED']
                filled_quantity = order_data['quantity']
            else:
                # 继续部分成交
                new_status = config.ORDER_STATUS['PARTIAL']
                additional_fill = remaining * random.uniform(0.1, 0.5)
                filled_quantity = current_filled + additional_fill
        
        else:
            # 已完成或已取消的订单不处理
            return True
        
        # 更新订单状态
        success = order_dao.update_order_status(order_id, new_status, filled_quantity)
        
        if success:
            # 记录状态变更日志
            order_dao.log_status_change(
                order_id, current_status, new_status,
                order_data.get('filled_quantity', 0), filled_quantity,
                f"自动处理-{self.worker_id}"
            )
            
            # 记录用户日志
            log_order_status_change(
                order_data['user_id'], order_id, 
                current_status, new_status, filled_quantity
            )
            
            # 发送订单事件
            event = OrderEvent(
                order_id=order_id,
                user_id=order_data['user_id'],
                group_id=order_data['group_id'],
                event_type='status_change',
                old_status=current_status,
                new_status=new_status,
                filled_quantity=filled_quantity
            )
            
            # 将事件推送到事件队列（用于实时响应）
            cache_service.push_order_to_queue({
                'type': 'order_event',
                'event': event.__dict__
            })
        
        return success


class MonitorWorker:
    """监控工作进程"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.processor = OrderProcessor(worker_id)
        self.user_order_manager = UserOrderManager()
        self.logger = None  # 延迟初始化，避免pickle问题
        self.is_running = False
        self.last_heartbeat = time.time()
    
    def _ensure_logger(self):
        """确保logger已初始化"""
        if self.logger is None:
            self.logger = get_system_logger()
    
    def start(self):
        """启动工作进程"""
        self.is_running = True
        self._ensure_logger()
        self.logger.info(f"监控工作进程 {self.worker_id} 启动")
        
        # 设置信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            self._run_monitor_loop()
        except Exception as e:
            self._ensure_logger()
            self.logger.error(f"工作进程 {self.worker_id} 异常退出: {e}")
        finally:
            self._ensure_logger()
            self.logger.info(f"监控工作进程 {self.worker_id} 停止")
    
    def stop(self):
        """停止工作进程"""
        self.is_running = False
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self._ensure_logger()
        self.logger.info(f"工作进程 {self.worker_id} 收到信号 {signum}，准备退出")
        self.stop()
    
    def _run_monitor_loop(self):
        """运行监控循环"""
        check_interval = config.MONITOR_CONFIG['check_interval']
        batch_size = config.MONITOR_CONFIG['batch_size']
        
        while self.is_running:
            try:
                # 更新心跳
                self._update_heartbeat()
                
                # 使用用户订单管理器获取下一个用户的订单
                user_id, orders = self.user_order_manager.get_next_user_orders(
                    worker_id=self.worker_id,
                    batch_size=batch_size
                )
                
                if user_id and orders:
                    self._ensure_logger()
                    self.logger.debug(f"工作进程 {self.worker_id} 为用户 {user_id} 获取到 {len(orders)} 个待处理订单")
                    
                    # 处理该用户的订单
                    processed_count = 0
                    for order in orders:
                        if not self.is_running:
                            break
                        if self.processor.process_order(order):
                            processed_count += 1
                    
                    # 释放用户锁
                    self.user_order_manager.release_user_lock(user_id, self.worker_id)
                    
                    self._ensure_logger()
                    self.logger.debug(f"工作进程 {self.worker_id} 为用户 {user_id} 处理了 {processed_count}/{len(orders)} 个订单")
                
                # 更新统计信息
                self._update_stats()
                
                # 等待下次检查
                time.sleep(check_interval)
                
            except Exception as e:
                self._ensure_logger()
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(1)  # 异常时短暂等待
    
    def _update_heartbeat(self):
        """更新心跳"""
        current_time = time.time()
        if current_time - self.last_heartbeat >= 30:  # 每30秒更新一次心跳
            cache_service.set_heartbeat(self.worker_id)
            self.last_heartbeat = current_time
    
    def _update_stats(self):
        """更新统计信息"""
        stats = {
            f'worker_{self.worker_id}_processed': self.processor.processed_count,
            f'worker_{self.worker_id}_errors': self.processor.error_count,
            f'worker_{self.worker_id}_last_update': int(time.time())
        }
        cache_service.update_monitor_stats(stats)


class MonitorEngine:
    """监控引擎主类"""
    
    def __init__(self, worker_count: Optional[int] = None, batch_size: Optional[int] = None):
        self.logger = get_system_logger()
        self.workers: List[multiprocessing.Process] = []
        self.is_running = False
        self.stats_thread = None
        self.max_workers = worker_count or config.MONITOR_CONFIG['max_workers']
        self.batch_size = batch_size or config.MONITOR_CONFIG['batch_size']
    
    def start(self):
        """启动监控引擎"""
        if self.is_running:
            self.logger.warning("监控引擎已在运行")
            return False
        
        self.is_running = True
        self.logger.info("启动订单监控引擎")
        
        # 启动工作进程
        self._start_workers()
        
        # 启动统计线程
        self._start_stats_thread()
        
        self.logger.info(f"监控引擎启动完成，工作进程数: {len(self.workers)}")
        return True
    
    def stop(self):
        """停止监控引擎"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("停止订单监控引擎")
        
        # 停止工作进程
        self._stop_workers()
        
        # 停止统计线程
        if self.stats_thread and self.stats_thread.is_alive():
            self.stats_thread.join(timeout=5)
        
        self.logger.info("监控引擎已停止")
    
    def _start_workers(self):
        """启动工作进程"""
        for i in range(self.max_workers):
            worker_id = f"worker_{i}_{uuid.uuid4().hex[:8]}"
            process = multiprocessing.Process(
                target=_worker_main_function,
                args=(worker_id,),
                name=worker_id
            )
            process.daemon = True
            process.start()
            self.workers.append(process)
            self.logger.info(f"启动工作进程: {worker_id} (PID: {process.pid})")
    
    def _stop_workers(self):
        """停止工作进程"""
        for process in self.workers:
            if process.is_alive():
                self.logger.info(f"停止工作进程: {process.name} (PID: {process.pid})")
                process.terminate()
                process.join(timeout=10)
                if process.is_alive():
                    self.logger.warning(f"强制终止工作进程: {process.name}")
                    process.kill()
        self.workers.clear()
    
    def _start_stats_thread(self):
        """启动统计线程"""
        self.stats_thread = threading.Thread(
            target=self._stats_loop,
            name="stats_thread",
            daemon=True
        )
        self.stats_thread.start()
    
    def _stats_loop(self):
        """统计信息循环"""
        while self.is_running:
            try:
                # 获取统计信息
                stats = cache_service.get_monitor_stats()
                active_workers = cache_service.get_active_workers()
                queue_length = cache_service.get_queue_length()
                
                # 计算总处理数和错误数
                total_processed = sum(
                    int(v) for k, v in stats.items() 
                    if k.endswith('_processed') and isinstance(v, (int, str)) and str(v).isdigit()
                )
                total_errors = sum(
                    int(v) for k, v in stats.items() 
                    if k.endswith('_errors') and isinstance(v, (int, str)) and str(v).isdigit()
                )
                
                # 更新全局统计
                global_stats = {
                    'total_processed': total_processed,
                    'total_errors': total_errors,
                    'active_workers': len(active_workers),
                    'queue_length': queue_length,
                    'last_stats_update': int(time.time())
                }
                cache_service.update_monitor_stats(global_stats)
                
                # 记录统计信息
                if total_processed > 0 or queue_length > 0:
                    self.logger.info(
                        f"监控统计 - 处理: {total_processed}, 错误: {total_errors}, "
                        f"活跃进程: {len(active_workers)}, 队列长度: {queue_length}"
                    )
                
                time.sleep(60)  # 每分钟更新一次统计
                
            except Exception as e:
                self.logger.error(f"统计循环异常: {e}")
                time.sleep(10)
    
    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        stats = cache_service.get_monitor_stats()
        active_workers = cache_service.get_active_workers()
        
        return {
            'is_running': self.is_running,
            'worker_count': len(self.workers),
            'active_workers': len(active_workers),
            'total_processed': stats.get('total_processed', 0),
            'total_errors': stats.get('total_errors', 0),
            'queue_length': stats.get('queue_length', 0),
            'last_update': stats.get('last_stats_update', 0)
        }


def _worker_main_function(worker_id: str):
    """独立的工作进程主函数，避免pickle序列化问题"""
    worker = MonitorWorker(worker_id)
    worker.start()


# 全局监控引擎实例
monitor_engine = MonitorEngine()