-- 高并发订单监控系统数据库表结构
-- MySQL 5.7.44 版本

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `strategy` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `strategy`;

-- 用户表
CREATE TABLE IF NOT EXISTS `users` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username` VARCHAR(50) NOT NULL COMMENT '用户名',
    `email` VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '用户状态: 0-禁用, 1-启用',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_status` (`status`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 订单表
CREATE TABLE IF NOT EXISTS `orders` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `strategy_id` BIGINT UNSIGNED NOT NULL COMMENT '策略ID',
    `order_no` VARCHAR(64) NOT NULL COMMENT '订单号',
    `symbol` VARCHAR(20) NOT NULL COMMENT '交易标的',
    `order_type` TINYINT NOT NULL COMMENT '订单类型: 1-买入, 2-卖出',
    `quantity` DECIMAL(20,8) NOT NULL COMMENT '数量',
    `price` DECIMAL(20,8) NOT NULL COMMENT '价格',
    `status` TINYINT NOT NULL DEFAULT 0 COMMENT '订单状态: 0-待处理, 1-部分成交, 2-完全成交, 3-已取消, 4-失败',
    `filled_quantity` DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '已成交数量',
    `avg_price` DECIMAL(20,8) DEFAULT NULL COMMENT '平均成交价格',
    `commission` DECIMAL(20,8) DEFAULT 0 COMMENT '手续费',
    `order_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
    `update_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `extra_data` JSON DEFAULT NULL COMMENT '扩展数据',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_strategy_id` (`strategy_id`),
    KEY `idx_status` (`status`),
    KEY `idx_symbol` (`symbol`),
    KEY `idx_order_time` (`order_time`),
    KEY `idx_user_strategy` (`user_id`, `strategy_id`),
    KEY `idx_user_status` (`user_id`, `status`),
    CONSTRAINT `fk_orders_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单表';

-- 用户策略表
CREATE TABLE IF NOT EXISTS `user_strategies` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '策略ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `strategy_name` VARCHAR(100) NOT NULL COMMENT '策略名称',
    `strategy_type` VARCHAR(50) NOT NULL COMMENT '策略类型',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '策略状态: 0-关闭, 1-开启, 2-暂停',
    `config` JSON DEFAULT NULL COMMENT '策略配置参数',
    `risk_config` JSON DEFAULT NULL COMMENT '风控配置',
    `performance_data` JSON DEFAULT NULL COMMENT '策略表现数据',
    `start_time` TIMESTAMP NULL DEFAULT NULL COMMENT '策略开始时间',
    `end_time` TIMESTAMP NULL DEFAULT NULL COMMENT '策略结束时间',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_strategy_type` (`strategy_type`),
    KEY `idx_user_status` (`user_id`, `status`),
    KEY `idx_start_time` (`start_time`),
    CONSTRAINT `fk_user_strategies_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户策略表';

-- 系统监控表（可选，用于记录系统状态）
CREATE TABLE IF NOT EXISTS `system_monitor` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID',
    `metric_name` VARCHAR(100) NOT NULL COMMENT '指标名称',
    `metric_value` DECIMAL(20,8) NOT NULL COMMENT '指标值',
    `metric_unit` VARCHAR(20) DEFAULT NULL COMMENT '指标单位',
    `tags` JSON DEFAULT NULL COMMENT '标签信息',
    `timestamp` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '时间戳',
    PRIMARY KEY (`id`),
    KEY `idx_metric_name` (`metric_name`),
    KEY `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统监控表';

-- 创建索引优化查询性能
-- 订单表复合索引
ALTER TABLE `orders` ADD INDEX `idx_user_symbol_status` (`user_id`, `symbol`, `status`);
ALTER TABLE `orders` ADD INDEX `idx_strategy_status_time` (`strategy_id`, `status`, `order_time`);

-- 用户策略表复合索引  
ALTER TABLE `user_strategies` ADD INDEX `idx_user_type_status` (`user_id`, `strategy_type`, `status`);

-- 插入测试数据（可选）
INSERT INTO `users` (`username`, `email`, `status`) VALUES 
('test_user_1', 'user1@example.com', 1),
('test_user_2', 'user2@example.com', 1),
('test_user_3', 'user3@example.com', 1);

INSERT INTO `user_strategies` (`user_id`, `strategy_name`, `strategy_type`, `status`, `config`) VALUES
(1, '趋势跟踪策略', 'trend_following', 1, '{"param1": "value1", "param2": "value2"}'),
(1, '均值回归策略', 'mean_reversion', 1, '{"param1": "value1", "param2": "value2"}'),
(2, '网格交易策略', 'grid_trading', 1, '{"param1": "value1", "param2": "value2"}'),
(3, '套利策略', 'arbitrage', 0, '{"param1": "value1", "param2": "value2"}');

-- 设置MySQL优化参数（需要管理员权限）
-- SET GLOBAL innodb_buffer_pool_size = 1073741824; -- 1GB
-- SET GLOBAL max_connections = 1000;
-- SET GLOBAL innodb_flush_log_at_trx_commit = 2;
-- SET GLOBAL sync_binlog = 0;