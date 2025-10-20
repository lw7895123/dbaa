"""
用户和订单分组状态监控机制
监控数据库中用户和分组状态变化，并触发相应事件
"""
import threading
import time
import uuid
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from dataclasses import dataclass

from .config import config
from .database import user_dao, order_group_dao, db_manager
from .redis_client import cache_service
from .logger import get_system_logger, log_user_status_change, log_group_status_change
from .event_handler import UserStatusEvent, GroupStatusEvent, event_monitor


@dataclass
class StatusSnapshot:
    """状态快照"""
    user_statuses: Dict[int, int]  # user_id -> status
    group_statuses: Dict[int, int]  # group_id -> status
    timestamp: datetime


class StatusChangeDetector:
    """状态变化检测器"""
    
    def __init__(self):
        self.logger = get_system_logger()
        self.last_snapshot: Optional[StatusSnapshot] = None
    
    def detect_changes(self, current_snapshot: StatusSnapshot) -> List[Dict[str, Any]]:
        """检测状态变化"""
        changes = []
        
        if self.last_snapshot is None:
            self.last_snapshot = current_snapshot
            return changes
        
        # 检测用户状态变化
        user_changes = self._detect_user_changes(current_snapshot)
        changes.extend(user_changes)
        
        # 检测分组状态变化
        group_changes = self._detect_group_changes(current_snapshot)
        changes.extend(group_changes)
        
        self.last_snapshot = current_snapshot
        return changes
    
    def _detect_user_changes(self, current_snapshot: StatusSnapshot) -> List[Dict[str, Any]]:
        """检测用户状态变化"""
        changes = []
        
        # 检查现有用户的状态变化
        for user_id, current_status in current_snapshot.user_statuses.items():
            old_status = self.last_snapshot.user_statuses.get(user_id)
            
            if old_status is not None and old_status != current_status:
                changes.append({
                    'type': 'user_status_change',
                    'user_id': user_id,
                    'old_status': old_status,
                    'new_status': current_status,
                    'timestamp': current_snapshot.timestamp
                })
        
        # 检查新增用户
        new_users = set(current_snapshot.user_statuses.keys()) - set(self.last_snapshot.user_statuses.keys())
        for user_id in new_users:
            changes.append({
                'type': 'user_added',
                'user_id': user_id,
                'status': current_snapshot.user_statuses[user_id],
                'timestamp': current_snapshot.timestamp
            })
        
        return changes
    
    def _detect_group_changes(self, current_snapshot: StatusSnapshot) -> List[Dict[str, Any]]:
        """检测分组状态变化"""
        changes = []
        
        # 检查现有分组的状态变化
        for group_id, current_status in current_snapshot.group_statuses.items():
            old_status = self.last_snapshot.group_statuses.get(group_id)
            
            if old_status is not None and old_status != current_status:
                changes.append({
                    'type': 'group_status_change',
                    'group_id': group_id,
                    'old_status': old_status,
                    'new_status': current_status,
                    'timestamp': current_snapshot.timestamp
                })
        
        # 检查新增分组
        new_groups = set(current_snapshot.group_statuses.keys()) - set(self.last_snapshot.group_statuses.keys())
        for group_id in new_groups:
            changes.append({
                'type': 'group_added',
                'group_id': group_id,
                'status': current_snapshot.group_statuses[group_id],
                'timestamp': current_snapshot.timestamp
            })
        
        return changes


class StatusMonitor:
    """状态监控器"""
    
    def __init__(self):
        self.logger = get_system_logger()
        self.detector = StatusChangeDetector()
        self.is_running = False
        self.monitor_thread = None
        self.check_interval = 5.0  # 5秒检查一次
        
        # 缓存用户和分组信息
        self.user_cache: Dict[int, Dict[str, Any]] = {}
        self.group_cache: Dict[int, Dict[str, Any]] = {}
    
    def start(self):
        """启动状态监控"""
        if self.is_running:
            self.logger.warning("状态监控器已在运行")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="status_monitor",
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("状态监控器已启动")
    
    def stop(self):
        """停止状态监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        
        self.logger.info("状态监控器已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 获取当前状态快照
                snapshot = self._take_snapshot()
                
                # 检测变化
                changes = self.detector.detect_changes(snapshot)
                
                # 处理变化
                if changes:
                    self._process_changes(changes)
                
                # 等待下次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"状态监控循环异常: {e}")
                time.sleep(5)  # 异常时等待更长时间
    
    def _take_snapshot(self) -> StatusSnapshot:
        """获取当前状态快照"""
        # 获取所有用户状态
        users = db_manager.execute_query("SELECT id, username, status FROM users")
        user_statuses = {}
        for user in users:
            user_id = user['id']
            user_statuses[user_id] = user['status']
            # 更新用户缓存
            self.user_cache[user_id] = user
        
        # 获取所有分组状态
        groups = db_manager.execute_query(
            "SELECT id, user_id, group_name, status FROM order_groups"
        )
        group_statuses = {}
        for group in groups:
            group_id = group['id']
            group_statuses[group_id] = group['status']
            # 更新分组缓存
            self.group_cache[group_id] = group
        
        return StatusSnapshot(
            user_statuses=user_statuses,
            group_statuses=group_statuses,
            timestamp=datetime.now()
        )
    
    def _process_changes(self, changes: List[Dict[str, Any]]):
        """处理状态变化"""
        for change in changes:
            try:
                change_type = change['type']
                
                if change_type == 'user_status_change':
                    self._handle_user_status_change(change)
                elif change_type == 'group_status_change':
                    self._handle_group_status_change(change)
                elif change_type == 'user_added':
                    self._handle_user_added(change)
                elif change_type == 'group_added':
                    self._handle_group_added(change)
                
            except Exception as e:
                self.logger.error(f"处理状态变化失败: {e}")
    
    def _handle_user_status_change(self, change: Dict[str, Any]):
        """处理用户状态变化"""
        user_id = change['user_id']
        old_status = change['old_status']
        new_status = change['new_status']
        
        user_info = self.user_cache.get(user_id, {})
        username = user_info.get('username', f'user_{user_id}')
        
        self.logger.info(f"检测到用户状态变化: {username}({user_id}) {old_status} -> {new_status}")
        
        # 记录日志
        log_user_status_change(user_id, username, old_status, new_status)
        
        # 创建并分发事件
        event = UserStatusEvent(
            event_id=str(uuid.uuid4()),
            event_type='user_status_change',
            timestamp=change['timestamp'],
            user_id=user_id,
            username=username,
            old_status=old_status,
            new_status=new_status
        )
        
        # 将事件推送到事件队列
        cache_service.lpush('events', {
            'type': 'user_status_change',
            'event': event.to_dict()
        })
        
        # 直接分发事件（同步处理）
        event_monitor.dispatcher.dispatch(event)
    
    def _handle_group_status_change(self, change: Dict[str, Any]):
        """处理分组状态变化"""
        group_id = change['group_id']
        old_status = change['old_status']
        new_status = change['new_status']
        
        group_info = self.group_cache.get(group_id, {})
        group_name = group_info.get('group_name', f'group_{group_id}')
        user_id = group_info.get('user_id', 0)
        
        self.logger.info(f"检测到分组状态变化: {group_name}({group_id}) {old_status} -> {new_status}")
        
        # 记录日志
        log_group_status_change(user_id, group_id, group_name, old_status, new_status)
        
        # 创建并分发事件
        event = GroupStatusEvent(
            event_id=str(uuid.uuid4()),
            event_type='group_status_change',
            timestamp=change['timestamp'],
            group_id=group_id,
            user_id=user_id,
            group_name=group_name,
            old_status=old_status,
            new_status=new_status
        )
        
        # 将事件推送到事件队列
        cache_service.lpush('events', {
            'type': 'group_status_change',
            'event': event.to_dict()
        })
        
        # 直接分发事件（同步处理）
        event_monitor.dispatcher.dispatch(event)
    
    def _handle_user_added(self, change: Dict[str, Any]):
        """处理新增用户"""
        user_id = change['user_id']
        status = change['status']
        
        user_info = self.user_cache.get(user_id, {})
        username = user_info.get('username', f'user_{user_id}')
        
        self.logger.info(f"检测到新用户: {username}({user_id}), 状态: {status}")
        
        # 初始化用户状态缓存
        cache_service.set_user_status(user_id, status)
    
    def _handle_group_added(self, change: Dict[str, Any]):
        """处理新增分组"""
        group_id = change['group_id']
        status = change['status']
        
        group_info = self.group_cache.get(group_id, {})
        group_name = group_info.get('group_name', f'group_{group_id}')
        user_id = group_info.get('user_id', 0)
        
        self.logger.info(f"检测到新分组: {group_name}({group_id}), 状态: {status}")
        
        # 初始化分组状态缓存
        cache_service.set_group_status(group_id, status)
    
    def force_refresh_cache(self):
        """强制刷新缓存"""
        try:
            self.logger.info("强制刷新状态缓存")
            
            # 刷新用户状态缓存
            users = db_manager.execute_query("SELECT id, status FROM users")
            for user in users:
                cache_service.set_user_status(user['id'], user['status'])
            
            # 刷新分组状态缓存
            groups = db_manager.execute_query("SELECT id, status FROM order_groups")
            for group in groups:
                cache_service.set_group_status(group['id'], group['status'])
            
            self.logger.info(f"缓存刷新完成: {len(users)}个用户, {len(groups)}个分组")
            
        except Exception as e:
            self.logger.error(f"刷新缓存失败: {e}")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        try:
            # 统计用户状态
            user_stats = db_manager.execute_query("""
                SELECT status, COUNT(*) as count 
                FROM users 
                GROUP BY status
            """)
            
            # 统计分组状态
            group_stats = db_manager.execute_query("""
                SELECT status, COUNT(*) as count 
                FROM order_groups 
                GROUP BY status
            """)
            
            return {
                'user_stats': {row['status']: row['count'] for row in user_stats},
                'group_stats': {row['status']: row['count'] for row in group_stats},
                'last_check': datetime.now().isoformat(),
                'is_running': self.is_running
            }
            
        except Exception as e:
            self.logger.error(f"获取状态摘要失败: {e}")
            return {}


class StatusController:
    """状态控制器 - 提供手动控制状态的接口"""
    
    def __init__(self):
        self.logger = get_system_logger()
    
    def update_user_status(self, user_id: int, status: int, reason: str = "") -> bool:
        """更新用户状态"""
        try:
            # 获取当前用户信息
            user = user_dao.get_user_by_id(user_id)
            if not user:
                self.logger.error(f"用户不存在: {user_id}")
                return False
            
            old_status = user['status']
            if old_status == status:
                self.logger.info(f"用户状态无变化: {user_id}")
                return True
            
            # 更新数据库
            success = user_dao.update_user_status(user_id, status)
            if success:
                self.logger.info(f"用户状态更新成功: {user_id} {old_status} -> {status}")
                if reason:
                    self.logger.info(f"更新原因: {reason}")
                
                # 立即更新缓存
                cache_service.set_user_status(user_id, status)
                
                return True
            else:
                self.logger.error(f"用户状态更新失败: {user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新用户状态异常: {e}")
            return False
    
    def update_group_status(self, group_id: int, status: int, reason: str = "") -> bool:
        """更新分组状态"""
        try:
            # 获取当前分组信息
            group = order_group_dao.get_group_by_id(group_id)
            if not group:
                self.logger.error(f"分组不存在: {group_id}")
                return False
            
            old_status = group['status']
            if old_status == status:
                self.logger.info(f"分组状态无变化: {group_id}")
                return True
            
            # 更新数据库
            success = order_group_dao.update_group_status(group_id, status)
            if success:
                self.logger.info(f"分组状态更新成功: {group_id} {old_status} -> {status}")
                if reason:
                    self.logger.info(f"更新原因: {reason}")
                
                # 立即更新缓存
                cache_service.set_group_status(group_id, status)
                
                return True
            else:
                self.logger.error(f"分组状态更新失败: {group_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新分组状态异常: {e}")
            return False
    
    def batch_update_user_groups_status(self, user_id: int, status: int, reason: str = "") -> int:
        """批量更新用户所有分组状态"""
        try:
            # 获取用户所有分组
            groups = db_manager.execute_query(
                "SELECT id FROM order_groups WHERE user_id = %s",
                (user_id,)
            )
            
            success_count = 0
            for group in groups:
                if self.update_group_status(group['id'], status, reason):
                    success_count += 1
            
            self.logger.info(f"批量更新用户分组状态完成: 用户{user_id}, 成功{success_count}/{len(groups)}")
            return success_count
            
        except Exception as e:
            self.logger.error(f"批量更新用户分组状态异常: {e}")
            return 0


# 全局实例
status_monitor = StatusMonitor()
status_controller = StatusController()