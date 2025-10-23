#!/usr/bin/env python3
"""
Redis连接测试脚本
用于验证Redis连接是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.redis_client import redis_manager, cache_service

def test_redis_connection():
    """测试Redis连接"""
    print("开始测试Redis连接...")
    
    try:
        # 测试基本连接
        client = redis_manager.get_client()
        print(f"✓ Redis客户端获取成功: {client}")
        
        # 测试ping
        result = client.ping()
        print(f"✓ Redis ping测试成功: {result}")
        
        # 测试基本操作
        redis_manager.set("test_key", "test_value")
        value = redis_manager.get("test_key")
        print(f"✓ Redis基本操作测试成功: {value}")
        
        # 测试哈希表操作
        test_stats = {
            "processed_orders": 100,
            "active_workers": 4,
            "queue_length": 50
        }
        redis_manager.hset("test_stats", test_stats)
        retrieved_stats = redis_manager.hgetall("test_stats")
        print(f"✓ Redis哈希表操作测试成功: {retrieved_stats}")
        
        # 测试缓存服务
        cache_service.update_monitor_stats(test_stats)
        stats = cache_service.get_monitor_stats()
        print(f"✓ 缓存服务测试成功: {stats}")
        
        # 清理测试数据
        redis_manager.delete("test_key", "test_stats", "monitor:stats")
        print("✓ 测试数据清理完成")
        
        print("\n🎉 所有Redis测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ Redis测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)