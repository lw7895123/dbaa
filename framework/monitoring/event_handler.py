# -*- coding: utf-8 -*-
"""
事件处理器
负责处理订单和策略相关的事件
"""
import threading
import queue
import time
import logging
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


class EventType(Enum):
    """事件类型枚举"""
    ORDER_UPDATE = "order_update"
    ORDER_FILL = "order_fill"
    ORDER_CANCEL = "order_cancel"
    STRATEGY_START = "strategy_start"
    STRATEGY_STOP = "strategy_stop"
    STRATEGY_UPDATE = "strategy_update"
    USER_ACTIVATE = "user_activate"
    USER_DEACTIVATE = "user_deactivate"
    SYSTEM_ERROR = "system_error"
    MARKET_DATA = "market_data"


@dataclass
class BaseEvent:
    """基础事件类"""
    event_type: EventType
    timestamp: datetime
    user_id: int
    data: Dict[str, Any]
    event_id: str = None
    
    def __post_init__(self):
        if self.event_id is None:
            self.event_id = f"{self.event_type.value}_{self.user_id}_{int(self.timestamp.timestamp() * 1000000)}"


class OrderEvent(BaseEvent):
    """订单事件"""
    
    def __init__(self, event_type: EventType, user_id: int, order_id: int, 
                 strategy_id: int, data: Dict[str, Any]):
        super().__init__(event_type, datetime.now(), user_id, data)
        self.order_id = order_id
        self.strategy_id = strategy_id


class StrategyEvent(BaseEvent):
    """策略事件"""
    
    def __init__(self, event_type: EventType, user_id: int, strategy_id: int, 
                 data: Dict[str, Any]):
        super().__init__(event_type, datetime.now(), user_id, data)
        self.strategy_id = strategy_id


class EventHandler:
    """事件处理器"""
    
    def __init__(self, max_workers: int = 10, queue_size: int = 10000):
        """
        初始化事件处理器
        
        Args:
            max_workers: 最大工作线程数
            queue_size: 事件队列大小
        """
        self.max_workers = max_workers
        self.queue_size = queue_size
        
        # 事件队列
        self.event_queue = queue.Queue(maxsize=queue_size)
        
        # 事件处理器映射
        self.event_handlers = {}  # {EventType: List[Callable]}
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EventHandler")
        
        # 控制标志
        self.running = False
        self.worker_threads = []
        
        # 统计信息
        self.stats = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'queue_size': 0,
            'start_time': None
        }
        
        self.logger = logging.getLogger(__name__)
        self.lock = threading.RLock()
        
        self.logger.info(f"事件处理器初始化: 最大工作线程 {max_workers}, 队列大小 {queue_size}")
    
    def register_handler(self, event_type: EventType, handler: Callable[[BaseEvent], None]) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        with self.lock:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = []
            self.event_handlers[event_type].append(handler)
        
        self.logger.info(f"注册事件处理器: {event_type.value}")
    
    def unregister_handler(self, event_type: EventType, handler: Callable[[BaseEvent], None]) -> None:
        """
        注销事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        with self.lock:
            if event_type in self.event_handlers:
                if handler in self.event_handlers[event_type]:
                    self.event_handlers[event_type].remove(handler)
                    if not self.event_handlers[event_type]:
                        del self.event_handlers[event_type]
        
        self.logger.info(f"注销事件处理器: {event_type.value}")
    
    def emit_event(self, event: BaseEvent) -> bool:
        """
        发送事件
        
        Args:
            event: 事件对象
            
        Returns:
            bool: 是否成功加入队列
        """
        try:
            if not self.running:
                self.logger.warning("事件处理器未运行，忽略事件")
                return False
            
            # 非阻塞方式加入队列
            self.event_queue.put_nowait(event)
            
            with self.lock:
                self.stats['total_events'] += 1
                self.stats['queue_size'] = self.event_queue.qsize()
            
            self.logger.debug(f"事件已加入队列: {event.event_type.value}, ID: {event.event_id}")
            return True
            
        except queue.Full:
            self.logger.error(f"事件队列已满，丢弃事件: {event.event_type.value}")
            return False
        except Exception as e:
            self.logger.error(f"发送事件失败: {e}")
            return False
    
    def emit_order_event(self, event_type: EventType, user_id: int, order_id: int, 
                        strategy_id: int, data: Dict[str, Any]) -> bool:
        """发送订单事件"""
        event = OrderEvent(event_type, user_id, order_id, strategy_id, data)
        return self.emit_event(event)
    
    def emit_strategy_event(self, event_type: EventType, user_id: int, 
                           strategy_id: int, data: Dict[str, Any]) -> bool:
        """发送策略事件"""
        event = StrategyEvent(event_type, user_id, strategy_id, data)
        return self.emit_event(event)
    
    def _process_event(self, event: BaseEvent) -> None:
        """
        处理单个事件
        
        Args:
            event: 事件对象
        """
        try:
            handlers = self.event_handlers.get(event.event_type, [])
            if not handlers:
                self.logger.debug(f"没有注册的处理器: {event.event_type.value}")
                return
            
            # 并行处理所有处理器
            futures = []
            for handler in handlers:
                future = self.executor.submit(self._safe_handle_event, handler, event)
                futures.append(future)
            
            # 等待所有处理器完成
            success_count = 0
            for future in as_completed(futures, timeout=30):
                try:
                    if future.result():
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"事件处理器执行异常: {e}")
            
            with self.lock:
                if success_count > 0:
                    self.stats['processed_events'] += 1
                else:
                    self.stats['failed_events'] += 1
            
            self.logger.debug(f"事件处理完成: {event.event_type.value}, 成功处理器: {success_count}/{len(handlers)}")
            
        except Exception as e:
            with self.lock:
                self.stats['failed_events'] += 1
            self.logger.error(f"处理事件失败: {event.event_type.value}, 错误: {e}")
    
    def _safe_handle_event(self, handler: Callable[[BaseEvent], None], event: BaseEvent) -> bool:
        """
        安全执行事件处理器
        
        Args:
            handler: 处理函数
            event: 事件对象
            
        Returns:
            bool: 是否成功处理
        """
        try:
            handler(event)
            return True
        except Exception as e:
            self.logger.error(f"事件处理器执行失败: {handler.__name__}, 事件: {event.event_type.value}, 错误: {e}")
            return False
    
    def _worker_loop(self) -> None:
        """工作线程循环"""
        thread_name = threading.current_thread().name
        self.logger.info(f"事件处理工作线程启动: {thread_name}")
        
        while self.running:
            try:
                # 从队列获取事件，超时1秒
                event = self.event_queue.get(timeout=1.0)
                
                # 处理事件
                self._process_event(event)
                
                # 标记任务完成
                self.event_queue.task_done()
                
                # 更新队列大小统计
                with self.lock:
                    self.stats['queue_size'] = self.event_queue.qsize()
                
            except queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                self.logger.error(f"工作线程异常: {thread_name}, 错误: {e}")
                time.sleep(0.1)  # 短暂休息避免快速循环
        
        self.logger.info(f"事件处理工作线程停止: {thread_name}")
    
    def start(self) -> None:
        """启动事件处理器"""
        if self.running:
            self.logger.warning("事件处理器已经在运行")
            return
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # 启动工作线程
        for i in range(self.max_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"EventWorker-{i+1}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)
        
        self.logger.info(f"事件处理器启动: {self.max_workers} 个工作线程")
    
    def stop(self, timeout: float = 30.0) -> None:
        """
        停止事件处理器
        
        Args:
            timeout: 停止超时时间（秒）
        """
        if not self.running:
            self.logger.warning("事件处理器未运行")
            return
        
        self.logger.info("正在停止事件处理器...")
        
        # 设置停止标志
        self.running = False
        
        # 等待队列中的事件处理完成
        try:
            self.event_queue.join()
            self.logger.info("队列中的事件已处理完成")
        except Exception as e:
            self.logger.error(f"等待队列完成失败: {e}")
        
        # 等待工作线程结束
        for thread in self.worker_threads:
            thread.join(timeout=timeout/len(self.worker_threads))
            if thread.is_alive():
                self.logger.warning(f"工作线程未能及时停止: {thread.name}")
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        self.worker_threads.clear()
        
        self.logger.info("事件处理器已停止")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.stats.copy()
            stats['queue_size'] = self.event_queue.qsize()
            stats['registered_handlers'] = {
                event_type.value: len(handlers) 
                for event_type, handlers in self.event_handlers.items()
            }
            stats['running'] = self.running
            stats['worker_threads'] = len(self.worker_threads)
            
            if stats['start_time']:
                stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
            
            return stats
    
    def clear_queue(self) -> int:
        """
        清空事件队列
        
        Returns:
            int: 清空的事件数量
        """
        count = 0
        try:
            while True:
                self.event_queue.get_nowait()
                count += 1
        except queue.Empty:
            pass
        
        self.logger.info(f"清空事件队列: {count} 个事件")
        return count
    
    def __repr__(self):
        return f"<EventHandler(workers={self.max_workers}, queue_size={self.queue_size}, running={self.running})>"


# 全局事件处理器实例
event_handler = EventHandler()