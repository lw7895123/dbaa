#!/usr/bin/env python3
"""
用户订单管理器测试脚本
测试按用户分组的订单处理功能
"""
import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.user_order_manager import UserOrderManager
from app.database import order_dao, user_dao
from app.redis_client import cache_service
from app.config import config
from app.logger import get_system_logger

logger = get_system_logger()

def test_user_order_manager():
    """测试用户订单管理器"""
    logger.info("开始测试用户订单管理器")
    
    # 创建用户订单管理器实例
    manager = UserOrderManager()
    
    # 测试获取活跃用户
    logger.info("测试获取活跃用户...")
    active_users = manager.get_active_users()
    logger.info(f"活跃用户数量: {len(active_users)}")
    
    if not active_users:
        logger.warning("没有活跃用户，无法进行订单测试")
        return
    
    # 测试获取用户订单
    test_user_id = active_users[0]
    logger.info(f"测试用户 {test_user_id} 的订单获取...")
    
    user_id, orders = manager.get_next_user_orders(
        worker_id="test_worker_1",
        batch_size=10
    )
    
    if user_id and orders:
        logger.info(f"成功获取用户 {user_id} 的 {len(orders)} 个订单")
        
        # 释放用户锁
        manager.release_user_lock(user_id, "test_worker_1")
        logger.info(f"释放用户 {user_id} 的锁")
    else:
        logger.info("没有获取到订单")

def test_concurrent_processing():
    """测试并发处理"""
    logger.info("开始测试并发处理")
    
    def worker_simulation(worker_id):
        """模拟工作进程"""
        manager = UserOrderManager()
        processed_users = []
        
        for i in range(5):  # 每个工作进程处理5轮
            user_id, orders = manager.get_next_user_orders(
                worker_id=worker_id,
                batch_size=5
            )
            
            if user_id and orders:
                logger.info(f"工作进程 {worker_id} 获取用户 {user_id} 的 {len(orders)} 个订单")
                processed_users.append(user_id)
                
                # 模拟处理时间
                time.sleep(0.1)
                
                # 释放用户锁
                manager.release_user_lock(user_id, worker_id)
                logger.info(f"工作进程 {worker_id} 释放用户 {user_id} 的锁")
            else:
                logger.info(f"工作进程 {worker_id} 没有获取到订单")
            
            time.sleep(0.05)  # 短暂等待
        
        return processed_users
    
    # 启动多个工作进程模拟
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            worker_id = f"test_worker_{i+1}"
            future = executor.submit(worker_simulation, worker_id)
            futures.append(future)
        
        # 等待所有工作进程完成
        results = []
        for future in futures:
            result = future.result()
            results.append(result)
        
        logger.info("并发测试完成")
        for i, processed_users in enumerate(results):
            logger.info(f"工作进程 test_worker_{i+1} 处理的用户: {processed_users}")

def test_user_fairness():
    """测试用户处理公平性"""
    logger.info("开始测试用户处理公平性")
    
    manager = UserOrderManager()
    user_process_count = {}
    
    # 模拟多轮处理
    for round_num in range(20):
        user_id, orders = manager.get_next_user_orders(
            worker_id="fairness_test_worker",
            batch_size=5
        )
        
        if user_id and orders:
            user_process_count[user_id] = user_process_count.get(user_id, 0) + 1
            manager.release_user_lock(user_id, "fairness_test_worker")
        
        time.sleep(0.01)
    
    logger.info("用户处理次数统计:")
    for user_id, count in user_process_count.items():
        logger.info(f"用户 {user_id}: {count} 次")

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("用户订单管理器测试开始")
        logger.info("=" * 50)
        
        # 基本功能测试
        test_user_order_manager()
        
        logger.info("-" * 30)
        
        # 并发处理测试
        test_concurrent_processing()
        
        logger.info("-" * 30)
        
        # 公平性测试
        test_user_fairness()
        
        logger.info("=" * 50)
        logger.info("用户订单管理器测试完成")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())