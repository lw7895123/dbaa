-- 数据库优化脚本
-- 为多用户并发订单处理添加索引优化

-- 1. 订单表索引优化
-- 为用户ID和状态组合创建复合索引，优化按用户查询待处理订单
CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);

-- 为用户ID、状态和优先级创建复合索引，支持排序查询
CREATE INDEX IF NOT EXISTS idx_orders_user_status_priority ON orders(user_id, status, priority DESC, created_at ASC);

-- 为分组ID和状态创建复合索引
CREATE INDEX IF NOT EXISTS idx_orders_group_status ON orders(group_id, status);

-- 为订单状态和创建时间创建索引，优化全局订单查询
CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at ASC);

-- 为订单ID和用户ID创建复合索引，优化订单更新操作
CREATE INDEX IF NOT EXISTS idx_orders_id_user ON orders(id, user_id);

-- 2. 用户表索引优化
-- 为用户状态创建索引，快速查找活跃用户
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- 为用户状态和更新时间创建复合索引
CREATE INDEX IF NOT EXISTS idx_users_status_updated ON users(status, updated_at DESC);

-- 3. 订单分组表索引优化
-- 为分组状态创建索引
CREATE INDEX IF NOT EXISTS idx_order_groups_status ON order_groups(status);

-- 为用户ID和分组状态创建复合索引
CREATE INDEX IF NOT EXISTS idx_order_groups_user_status ON order_groups(user_id, status);

-- 为分组状态和更新时间创建复合索引
CREATE INDEX IF NOT EXISTS idx_order_groups_status_updated ON order_groups(status, updated_at DESC);

-- 4. 订单状态变更日志表索引优化（如果存在）
-- 为订单ID和变更时间创建复合索引
CREATE INDEX IF NOT EXISTS idx_order_status_log_order_time ON order_status_log(order_id, changed_at DESC);

-- 为用户ID和变更时间创建复合索引
CREATE INDEX IF NOT EXISTS idx_order_status_log_user_time ON order_status_log(user_id, changed_at DESC);

-- 5. 性能优化建议
-- 定期分析表统计信息
-- ANALYZE TABLE orders;
-- ANALYZE TABLE users;
-- ANALYZE TABLE order_groups;

-- 6. 查询优化提示
/*
优化后的查询示例：

1. 按用户查询待处理订单（支持状态列表）：
SELECT * FROM orders 
WHERE user_id = ? AND status IN ('PENDING', 'PARTIAL') 
ORDER BY priority DESC, created_at ASC 
LIMIT ?;

2. 查询活跃用户：
SELECT id FROM users WHERE status = 1;

3. 查询用户的活跃分组：
SELECT * FROM order_groups 
WHERE user_id = ? AND status = 1;

4. 全局待处理订单查询（如果仍需要）：
SELECT o.*, u.status as user_status, g.status as group_status
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN order_groups g ON o.group_id = g.id
WHERE o.status IN ('PENDING', 'PARTIAL')
  AND u.status = 1
  AND g.status = 1
ORDER BY o.priority DESC, o.created_at ASC
LIMIT ?;
*/

-- 7. 监控查询性能
/*
使用以下查询监控慢查询：

-- 查看当前运行的查询
SHOW PROCESSLIST;

-- 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 查看索引使用情况
SHOW INDEX FROM orders;
SHOW INDEX FROM users;
SHOW INDEX FROM order_groups;
*/