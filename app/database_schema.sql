-- 高并发订单监控系统数据库表结构
-- MySQL 5.7.44 版本

-- 用户表
CREATE TABLE `users` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `email` varchar(100) DEFAULT NULL COMMENT '邮箱',
  `phone` varchar(20) DEFAULT NULL COMMENT '手机号',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '用户状态：0-禁用，1-启用',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 订单分组表
CREATE TABLE `order_groups` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '分组ID',
  `user_id` bigint(20) NOT NULL COMMENT '用户ID',
  `group_name` varchar(100) NOT NULL COMMENT '分组名称',
  `group_code` varchar(50) NOT NULL COMMENT '分组编码',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '分组状态：0-关闭，1-开启',
  `description` text COMMENT '分组描述',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_group_code` (`user_id`, `group_code`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_updated_at` (`updated_at`),
  CONSTRAINT `fk_order_groups_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单分组表';

-- 订单表
CREATE TABLE `orders` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  `user_id` bigint(20) NOT NULL COMMENT '用户ID',
  `group_id` bigint(20) NOT NULL COMMENT '分组ID',
  `order_no` varchar(50) NOT NULL COMMENT '订单号',
  `order_type` varchar(20) NOT NULL COMMENT '订单类型：BUY-买入，SELL-卖出',
  `symbol` varchar(20) NOT NULL COMMENT '交易标的',
  `price` decimal(18,8) NOT NULL COMMENT '价格',
  `quantity` decimal(18,8) NOT NULL COMMENT '数量',
  `filled_quantity` decimal(18,8) NOT NULL DEFAULT '0.00000000' COMMENT '已成交数量',
  `status` varchar(20) NOT NULL DEFAULT 'PENDING' COMMENT '订单状态：PENDING-待成交，PARTIAL-部分成交，FILLED-完全成交，CANCELLED-已取消',
  `priority` int(11) NOT NULL DEFAULT '0' COMMENT '优先级：数字越大优先级越高',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `filled_at` timestamp NULL DEFAULT NULL COMMENT '成交时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_group_id` (`group_id`),
  KEY `idx_status` (`status`),
  KEY `idx_symbol` (`symbol`),
  KEY `idx_updated_at` (`updated_at`),
  KEY `idx_priority_created` (`priority`, `created_at`),
  CONSTRAINT `fk_orders_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_orders_group_id` FOREIGN KEY (`group_id`) REFERENCES `order_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 订单状态变更日志表（用于监控和审计）
CREATE TABLE `order_status_logs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `order_id` bigint(20) NOT NULL COMMENT '订单ID',
  `old_status` varchar(20) DEFAULT NULL COMMENT '原状态',
  `new_status` varchar(20) NOT NULL COMMENT '新状态',
  `old_filled_quantity` decimal(18,8) DEFAULT '0.00000000' COMMENT '原已成交数量',
  `new_filled_quantity` decimal(18,8) DEFAULT '0.00000000' COMMENT '新已成交数量',
  `change_reason` varchar(200) DEFAULT NULL COMMENT '变更原因',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_order_status_logs_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单状态变更日志表';

-- 创建索引以优化查询性能
-- 复合索引用于高频查询
CREATE INDEX `idx_orders_user_group_status` ON `orders` (`user_id`, `group_id`, `status`);
CREATE INDEX `idx_orders_status_updated` ON `orders` (`status`, `updated_at`);

-- 插入测试数据
INSERT INTO `users` (`username`, `email`, `phone`, `status`) VALUES
('user001', 'user001@example.com', '13800138001', 1),
('user002', 'user002@example.com', '13800138002', 1),
('user003', 'user003@example.com', '13800138003', 0);

INSERT INTO `order_groups` (`user_id`, `group_name`, `group_code`, `status`, `description`) VALUES
(1, '主要交易组', 'MAIN_GROUP', 1, '用户主要的交易订单分组'),
(1, '备用交易组', 'BACKUP_GROUP', 0, '备用的交易订单分组'),
(2, '高频交易组', 'HIGH_FREQ', 1, '高频交易专用分组'),
(3, '测试分组', 'TEST_GROUP', 1, '测试用分组');