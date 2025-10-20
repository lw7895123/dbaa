# 高并发订单监控系统

一个基于Python的高性能订单监控系统，支持实时监控上千个用户订单，具备高并发处理能力和完整的状态管理机制。

## 系统特性

- ✅ **高并发处理**: 多进程架构，支持上千用户订单实时监控
- ✅ **实时状态监控**: 监控用户和订单分组状态变化，自动触发相应事件
- ✅ **灵活的状态控制**: 支持用户级别和分组级别的订单监控开关
- ✅ **完整的日志系统**: 每个用户独立日志文件，自动清理过期日志
- ✅ **事件驱动架构**: 基于事件的异步处理机制
- ✅ **数据库连接池**: 高效的MySQL连接池管理
- ✅ **Redis缓存**: 高性能缓存和消息队列
- ✅ **优雅关闭**: 支持信号处理和优雅关闭

## 技术栈

- **Python 3.7.9**
- **MySQL 5.7.44**: 主数据库
- **Redis**: 缓存和消息队列
- **多进程**: 高并发处理
- **事件驱动**: 异步事件处理

## 项目结构

```
dbaa/
├── main.py                 # 主启动文件
├── requirements.txt        # 依赖包列表
├── README.md              # 项目文档
└── app/                   # 应用核心代码
    ├── config.py          # 配置管理
    ├── database.py        # 数据库连接和DAO
    ├── redis_client.py    # Redis客户端管理
    ├── logger.py          # 日志管理系统
    ├── monitor_engine.py  # 订单监控核心引擎
    ├── event_handler.py   # 事件处理机制
    ├── status_monitor.py  # 状态监控机制
    └── database_schema.sql # 数据库表结构
```

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Python 3.7.9
- MySQL 5.7.44
- Redis

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境配置

1. 复制环境配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，配置数据库和Redis连接信息：
```bash
# MySQL配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=order_monitor

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# 监控配置
MONITOR_INTERVAL=5
BATCH_SIZE=100
MAX_WORKERS=4

# 日志配置
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=7
```

### 4. 数据库配置

1. 创建数据库：
```sql
CREATE DATABASE order_monitor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 导入表结构：
```bash
mysql -u username -p order_monitor < app/database_schema.sql
```

### 5. 启动系统

```bash
# 测试连接
python main.py --test

# 初始化缓存
python main.py --init-cache

# 启动系统
python main.py
```

## 使用说明

### 命令行参数

```bash
python main.py                    # 启动系统
python main.py --test             # 测试连接
python main.py --status           # 显示状态
python main.py --init-cache       # 初始化缓存
python main.py --log-level DEBUG  # 设置日志级别
```

### 状态控制

系统支持通过数据库直接控制监控状态：

1. **用户级别控制**：
```sql
-- 启用用户监控
UPDATE users SET status = 1 WHERE id = 1;

-- 禁用用户监控
UPDATE users SET status = 0 WHERE id = 1;
```

2. **分组级别控制**：
```sql
-- 启用分组监控
UPDATE order_groups SET status = 1 WHERE id = 1;

-- 禁用分组监控
UPDATE order_groups SET status = 0 WHERE id = 1;
```

### 日志管理

- **系统日志**: `logs/system.log`
- **用户日志**: `logs/users/user_{user_id}.log`
- **自动清理**: 保留最近7天的日志文件

## 数据库表结构

### users 表
用户基础信息表，包含用户状态控制字段。

### order_groups 表
订单分组表，每个用户可以有多个分组，支持分组级别的状态控制。

### orders 表
订单详情表，包含订单状态和处理时间等信息。

### order_status_logs 表
订单状态变更日志表，记录所有状态变化历史。

## 系统架构

### 核心组件

1. **MonitorEngine**: 订单监控核心引擎
   - 多进程工作模式
   - 批量处理订单
   - 自动负载均衡

2. **StatusMonitor**: 状态监控器
   - 实时监控用户和分组状态变化
   - 自动触发状态变更事件

3. **EventHandler**: 事件处理器
   - 异步事件处理
   - 支持多种事件类型
   - 线程池处理

4. **CacheService**: 缓存服务
   - Redis连接池管理
   - 状态缓存
   - 消息队列

### 工作流程

1. **启动阶段**：
   - 初始化数据库连接池
   - 启动Redis连接
   - 加载用户和分组状态到缓存
   - 启动监控进程

2. **监控阶段**：
   - 工作进程定期获取待处理订单
   - 检查用户和分组状态
   - 处理符合条件的订单
   - 更新订单状态和日志

3. **事件处理**：
   - 监控数据库状态变化
   - 触发相应事件
   - 异步处理事件响应

## 性能优化

### 数据库优化
- 使用连接池减少连接开销
- 批量操作提高处理效率
- 索引优化查询性能

### 缓存优化
- Redis缓存热点数据
- 减少数据库查询频率
- 消息队列异步处理

### 并发优化
- 多进程处理提高并发能力
- 工作进程负载均衡
- 异步事件处理

## 监控和运维

### 系统监控
- 进程状态监控
- 性能指标统计
- 错误日志记录

### 运维工具
- 优雅关闭机制
- 状态查询命令
- 缓存管理工具

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MySQL服务状态
   - 验证连接配置
   - 确认网络连通性

2. **Redis连接失败**
   - 检查Redis服务状态
   - 验证连接配置
   - 确认防火墙设置

3. **进程启动失败**
   - 检查端口占用
   - 查看错误日志
   - 验证权限设置

### 日志分析
- 系统日志：`logs/system.log`
- 错误日志：查看ERROR级别日志
- 性能日志：查看统计信息

## 开发指南

### 添加新功能
1. 在相应模块中添加代码
2. 更新配置文件
3. 添加单元测试
4. 更新文档

### 代码规范
- 遵循PEP 8规范
- 添加类型注解
- 编写文档字符串
- 单元测试覆盖

## 许可证

本项目采用 MIT 许可证。

## 联系方式

如有问题或建议，请联系开发团队。
