"""
订单事件处理和实时响应机制
处理订单状态变化、用户状态变化等事件
"""
import asyncio
import threading
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod

from .config import config
from .database import order_dao, user_dao, order_group_dao
from .redis_client import cache_service
from .logger import get_system_logger, get_user_logger, log_order_event


@dataclass
class BaseEvent:
    """基础事件类"""
    event_id: str
    event_type: str
    timestamp: datetime
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class OrderStatusEvent(BaseEvent):
    """订单状态变化事件"""
    order_id: int
    user_id: int
    group_id: int
    old_status: str
    new_status: str
    filled_quantity: Optional[float] = None
    price: Optional[float] = None
    symbol: Optional[str] = None


@dataclass
class UserStatusEvent(BaseEvent):
    """用户状态变化事件"""
    user_id: int
    username: str
    old_status: int
    new_status: int


@dataclass
class GroupStatusEvent(BaseEvent):
    """分组状态变化事件"""
    group_id: int
    user_id: int
    group_name: str
    old_status: int
    new_status: int


class EventHandler(ABC):
    """事件处理器抽象基类"""
    
    @abstractmethod
    def handle(self, event: BaseEvent) -> bool:
        """处理事件"""
        pass
    
    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """检查是否能处理指定类型的事件"""
        pass


class OrderStatusHandler(EventHandler):
    """订单状态变化处理器"""
    
    def __init__(self):
        self.logger = get_system_logger()
    
    def can_handle(self, event_type: str) -> bool:
        return event_type == "order_status_change"
    
    def handle(self, event: OrderStatusEvent) -> bool:
        """处理订单状态变化事件"""
        try:
            self.logger.info(
                f"处理订单状态变化事件: 订单[{event.order_id}] "
                f"{event.old_status} -> {event.new_status}"
            )
            
            # 记录用户日志
            user_logger = get_user_logger(event.user_id)
            message = f"订单[{event.order_id}] 状态变更: {event.old_status} -> {event.new_status}"
            if event.filled_quantity is not None:
                message += f", 成交数量: {event.filled_quantity}"
            if event.symbol:
                message += f", 交易标的: {event.symbol}"
            user_logger.info(message)
            
            # 如果订单完全成交，执行特殊处理
            if event.new_status == config.ORDER_STATUS['FILLED']:
                self._handle_order_filled(event)
            
            # 如果订单部分成交，执行部分成交处理
            elif event.new_status == config.ORDER_STATUS['PARTIAL']:
                self._handle_order_partial_filled(event)
            
            # 更新缓存中的订单状态
            self._update_order_cache(event)
            
            # 发送通知（可以扩展为邮件、短信、webhook等）
            self._send_notification(event)
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理订单状态变化事件失败: {e}")
            return False
    
    def _handle_order_filled(self, event: OrderStatusEvent):
        """处理订单完全成交"""
        self.logger.info(f"订单[{event.order_id}]完全成交，数量: {event.filled_quantity}")
        
        # 记录成交事件
        log_order_event(
            event.user_id, event.order_id, "完全成交",
            f"成交数量: {event.filled_quantity}, 价格: {event.price}"
        )
        
        # 可以在这里添加成交后的业务逻辑
        # 例如：风险控制、资金结算、持仓更新等
    
    def _handle_order_partial_filled(self, event: OrderStatusEvent):
        """处理订单部分成交"""
        self.logger.info(f"订单[{event.order_id}]部分成交，数量: {event.filled_quantity}")
        
        # 记录部分成交事件
        log_order_event(
            event.user_id, event.order_id, "部分成交",
            f"成交数量: {event.filled_quantity}, 价格: {event.price}"
        )
    
    def _update_order_cache(self, event: OrderStatusEvent):
        """更新订单缓存"""
        # 这里可以更新Redis中的订单状态缓存
        cache_key = f"order:status:{event.order_id}"
        cache_service.set(cache_key, {
            'status': event.new_status,
            'filled_quantity': event.filled_quantity,
            'updated_at': event.timestamp.isoformat()
        }, ex=3600)
    
    def _send_notification(self, event: OrderStatusEvent):
        """发送通知"""
        # 这里可以实现各种通知方式
        # 例如：WebSocket推送、邮件通知、短信通知等
        notification_data = {
            'type': 'order_status_change',
            'order_id': event.order_id,
            'user_id': event.user_id,
            'old_status': event.old_status,
            'new_status': event.new_status,
            'filled_quantity': event.filled_quantity,
            'timestamp': event.timestamp.isoformat()
        }
        
        # 推送到通知队列
        cache_service.lpush('notifications', notification_data)


class UserStatusHandler(EventHandler):
    """用户状态变化处理器"""
    
    def __init__(self):
        self.logger = get_system_logger()
    
    def can_handle(self, event_type: str) -> bool:
        return event_type == "user_status_change"
    
    def handle(self, event: UserStatusEvent) -> bool:
        """处理用户状态变化事件"""
        try:
            status_map = {0: "禁用", 1: "启用"}
            old_status_text = status_map.get(event.old_status, str(event.old_status))
            new_status_text = status_map.get(event.new_status, str(event.new_status))
            
            self.logger.info(
                f"处理用户状态变化事件: 用户[{event.user_id}:{event.username}] "
                f"{old_status_text} -> {new_status_text}"
            )
            
            # 更新用户状态缓存
            cache_service.set_user_status(event.user_id, event.new_status)
            
            # 记录用户日志
            user_logger = get_user_logger(event.user_id)
            user_logger.info(f"用户状态变更: {old_status_text} -> {new_status_text}")
            
            # 如果用户被禁用，停止其所有订单监控
            if event.new_status == config.USER_STATUS['DISABLED']:
                self._disable_user_monitoring(event.user_id)
            
            # 如果用户被启用，恢复其订单监控
            elif event.new_status == config.USER_STATUS['ENABLED']:
                self._enable_user_monitoring(event.user_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理用户状态变化事件失败: {e}")
            return False
    
    def _disable_user_monitoring(self, user_id: int):
        """禁用用户监控"""
        self.logger.info(f"禁用用户[{user_id}]的订单监控")
        
        # 获取用户的所有分组并更新缓存状态
        groups = order_group_dao.get_user_active_groups(user_id)
        for group in groups:
            cache_service.set_group_status(group['id'], config.GROUP_STATUS['CLOSED'])
        
        log_order_event(user_id, 0, "用户监控禁用", f"影响分组数: {len(groups)}")
    
    def _enable_user_monitoring(self, user_id: int):
        """启用用户监控"""
        self.logger.info(f"启用用户[{user_id}]的订单监控")
        
        # 重新加载用户的活跃分组状态
        groups = order_group_dao.get_user_active_groups(user_id)
        for group in groups:
            cache_service.set_group_status(group['id'], group['status'])
        
        log_order_event(user_id, 0, "用户监控启用", f"活跃分组数: {len(groups)}")


class GroupStatusHandler(EventHandler):
    """分组状态变化处理器"""
    
    def __init__(self):
        self.logger = get_system_logger()
    
    def can_handle(self, event_type: str) -> bool:
        return event_type == "group_status_change"
    
    def handle(self, event: GroupStatusEvent) -> bool:
        """处理分组状态变化事件"""
        try:
            status_map = {0: "关闭", 1: "开启"}
            old_status_text = status_map.get(event.old_status, str(event.old_status))
            new_status_text = status_map.get(event.new_status, str(event.new_status))
            
            self.logger.info(
                f"处理分组状态变化事件: 分组[{event.group_id}:{event.group_name}] "
                f"{old_status_text} -> {new_status_text}"
            )
            
            # 更新分组状态缓存
            cache_service.set_group_status(event.group_id, event.new_status)
            
            # 记录用户日志
            user_logger = get_user_logger(event.user_id)
            user_logger.info(f"分组[{event.group_name}]状态变更: {old_status_text} -> {new_status_text}")
            
            # 如果分组被关闭，记录影响的订单数
            if event.new_status == config.GROUP_STATUS['CLOSED']:
                self._handle_group_closed(event)
            
            # 如果分组被开启，记录活跃订单数
            elif event.new_status == config.GROUP_STATUS['OPEN']:
                self._handle_group_opened(event)
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理分组状态变化事件失败: {e}")
            return False
    
    def _handle_group_closed(self, event: GroupStatusEvent):
        """处理分组关闭"""
        # 统计分组中的活跃订单数
        pending_orders = order_dao.get_group_orders(event.group_id, config.ORDER_STATUS['PENDING'])
        partial_orders = order_dao.get_group_orders(event.group_id, config.ORDER_STATUS['PARTIAL'])
        
        total_affected = len(pending_orders) + len(partial_orders)
        
        log_order_event(
            event.user_id, 0, "分组监控关闭",
            f"分组: {event.group_name}, 影响订单数: {total_affected}"
        )
    
    def _handle_group_opened(self, event: GroupStatusEvent):
        """处理分组开启"""
        # 统计分组中的活跃订单数
        pending_orders = order_dao.get_group_orders(event.group_id, config.ORDER_STATUS['PENDING'])
        partial_orders = order_dao.get_group_orders(event.group_id, config.ORDER_STATUS['PARTIAL'])
        
        total_active = len(pending_orders) + len(partial_orders)
        
        log_order_event(
            event.user_id, 0, "分组监控开启",
            f"分组: {event.group_name}, 活跃订单数: {total_active}"
        )


class EventDispatcher:
    """事件分发器"""
    
    def __init__(self):
        self.handlers: List[EventHandler] = []
        self.logger = get_system_logger()
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="event_handler")
        
        # 注册默认处理器
        self.register_handler(OrderStatusHandler())
        self.register_handler(UserStatusHandler())
        self.register_handler(GroupStatusHandler())
    
    def register_handler(self, handler: EventHandler):
        """注册事件处理器"""
        self.handlers.append(handler)
        self.logger.info(f"注册事件处理器: {handler.__class__.__name__}")
    
    def dispatch(self, event: BaseEvent) -> bool:
        """分发事件"""
        try:
            # 找到能处理该事件的处理器
            suitable_handlers = [
                handler for handler in self.handlers
                if handler.can_handle(event.event_type)
            ]
            
            if not suitable_handlers:
                self.logger.warning(f"没有找到处理器处理事件类型: {event.event_type}")
                return False
            
            # 异步处理事件
            futures = []
            for handler in suitable_handlers:
                future = self.executor.submit(handler.handle, event)
                futures.append(future)
            
            # 等待所有处理器完成
            success_count = 0
            for future in futures:
                try:
                    if future.result(timeout=30):  # 30秒超时
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"事件处理器执行失败: {e}")
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"事件分发失败: {e}")
            return False
    
    def shutdown(self):
        """关闭事件分发器"""
        self.executor.shutdown(wait=True)


class EventMonitor:
    """事件监控器"""
    
    def __init__(self):
        self.dispatcher = EventDispatcher()
        self.logger = get_system_logger()
        self.is_running = False
        self.monitor_thread = None
    
    def start(self):
        """启动事件监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="event_monitor",
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("事件监控器已启动")
    
    def stop(self):
        """停止事件监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        
        self.dispatcher.shutdown()
        self.logger.info("事件监控器已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 从Redis队列获取事件
                event_data = cache_service.pop_order_from_queue()
                
                if event_data and isinstance(event_data, dict):
                    event = self._parse_event(event_data)
                    if event:
                        self.dispatcher.dispatch(event)
                else:
                    # 没有事件时短暂休眠
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"事件监控循环异常: {e}")
                time.sleep(1)
    
    def _parse_event(self, event_data: Dict[str, Any]) -> Optional[BaseEvent]:
        """解析事件数据"""
        try:
            event_type = event_data.get('type')
            
            if event_type == 'order_event':
                event_info = event_data.get('event', {})
                return OrderStatusEvent(
                    event_id=event_info.get('event_id', ''),
                    event_type='order_status_change',
                    timestamp=datetime.fromisoformat(event_info.get('timestamp', datetime.now().isoformat())),
                    order_id=event_info.get('order_id'),
                    user_id=event_info.get('user_id'),
                    group_id=event_info.get('group_id'),
                    old_status=event_info.get('old_status'),
                    new_status=event_info.get('new_status'),
                    filled_quantity=event_info.get('filled_quantity')
                )
            
            # 可以添加更多事件类型的解析
            
        except Exception as e:
            self.logger.error(f"解析事件数据失败: {e}")
        
        return None


# 全局事件监控器实例
event_monitor = EventMonitor()