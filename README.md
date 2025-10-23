# 高并发订单监控系统

一个基于Python的高性能订单监控系统，支持实时监控上千个用户订单，具备高并发处理能力和完整的状态管理机制。采用模块化框架设计，提供完整的监控、日志、策略管理功能。

## 系统特性

- ✅ **高并发处理**: 多线程架构，支持上千用户订单实时监控
- ✅ **实时状态监控**: 监控用户和订单状态变化，自动触发相应事件
- ✅ **灵活的策略管理**: 支持用户自定义策略，可插拔的策略框架
- ✅ **完整的日志系统**: 每个用户独立日志文件，7天自动清理
- ✅ **事件驱动架构**: 基于事件的异步处理机制
- ✅ **数据库连接池**: 高效的MySQL连接池管理
- ✅ **Redis缓存**: 高性能缓存和消息队列
- ✅ **模块化设计**: 清晰的框架结构，易于扩展和维护
- ✅ **优雅关闭**: 支持信号处理和优雅关闭

## 技术栈

- **Python 3.7+**
- **MySQL**: 主数据库，存储用户、订单、策略数据
- **Redis**: 缓存和消息队列
- **多线程**: 高并发处理
- **事件驱动**: 异步事件处理
- **模块化框架**: 清晰的代码组织结构

## 项目结构

```
dbaa/
├── app.py                    # 主应用启动文件
├── setup.py                  # 系统安装脚本
├── start.bat                 # Windows启动脚本
├── start.sh                  # Linux/Mac启动脚本
├── requirements.txt          # 依赖包列表
├── .env.example             # 环境配置模板
├── README.md                # 项目文档
├── logs/                    # 日志目录
│   ├── system.log          # 系统日志
│   └── users/              # 用户日志目录
└── framework/              # 核心框架
    ├── __init__.py
    ├── config/             # 配置模块
    │   ├── __init__.py
    │   └── settings.py     # 系统配置
    ├── database/           # 数据库模块
    │   ├── __init__.py
    │   ├── mysql_manager.py    # MySQL连接池管理
    │   ├── redis_manager.py    # Redis连接池管理
    │   └── schema.sql          # 数据库表结构
    ├── models/             # 数据模型
    │   ├── __init__.py
    │   ├── user.py         # 用户模型
    │   ├── order.py        # 订单模型
    │   └── strategy.py     # 策略模型
    ├── strategies/         # 策略模块
    │   ├── __init__.py
    │   ├── base_strategy.py    # 策略基类
    │   └── strategy_manager.py # 策略管理器
    ├── monitoring/         # 监控模块
    │   ├── __init__.py
    │   ├── monitoring_engine.py # 监控引擎
    │   ├── event_handler.py     # 事件处理器
    │   └── user_monitor.py      # 用户监控器
    ├── logging/            # 日志模块
    │   ├── __init__.py
    │   ├── user_logger.py      # 用户日志器
    │   ├── log_manager.py      # 日志管理器
    │   └── log_cleaner.py      # 日志清理器
    └── utils/              # 工具模块
        ├── __init__.py
        └── user_order_manager.py # 用户订单管理器
```

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Python 3.7+
- MySQL 5.7+
- Redis 5.0+

### 2. 自动安装（推荐）

使用自动安装脚本一键安装：

```bash
# 克隆项目
git clone <repository-url>
cd dbaa

# 运行安装脚本
python setup.py
```

安装脚本将自动完成：
- 创建虚拟环境
- 安装所有依赖
- 创建必要目录
- 生成配置文件模板

### 3. 手动安装

如果需要手动安装：

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 环境配置

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
MYSQL_DATABASE=order_monitoring

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# 日志配置
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=7

# 监控配置
MONITORING_ENABLED=true
MONITORING_SCAN_INTERVAL=10
```

### 5. 数据库配置

1. 创建数据库：
```sql
CREATE DATABASE order_monitoring CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 导入表结构：
```bash
mysql -u username -p order_monitoring < framework/database/schema.sql
```

### 6. 启动系统

#### 使用启动脚本（推荐）

**Windows:**
```cmd
# 启动系统
start.bat start

# 查看状态
start.bat status

# 停止系统
start.bat stop
```

**Linux/Mac:**
```bash
# 给脚本执行权限
chmod +x start.sh

# 启动系统
./start.sh start

# 查看状态
./start.sh status

# 停止系统
./start.sh stop
```

#### 直接使用Python

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 测试系统
python app.py test

# 启动系统
python app.py start

# 查看状态
python app.py status
```

## 使用说明

### 命令行参数

```bash
# 基本命令
python app.py start               # 启动系统（阻塞模式）
python app.py status              # 显示系统状态
python app.py test                # 测试系统依赖和连接

# 启动脚本命令
start.bat start                   # Windows启动
start.bat stop                    # Windows停止
start.bat restart                 # Windows重启
start.bat status                  # Windows状态查询
start.bat test                    # Windows测试
start.bat install                 # Windows安装依赖

./start.sh start                  # Linux/Mac启动
./start.sh stop                   # Linux/Mac停止
./start.sh restart                # Linux/Mac重启
./start.sh status                 # Linux/Mac状态查询
./start.sh test                   # Linux/Mac测试
./start.sh logs                   # Linux/Mac查看日志
./start.sh install                # Linux/Mac安装依赖
```

### 系统架构

系统采用模块化设计，主要组件包括：

1. **监控引擎** (`MonitoringEngine`): 管理所有用户的监控器
2. **用户监控器** (`UserMonitor`): 监控单个用户的策略和订单
3. **策略管理器** (`StrategyManager`): 管理用户的交易策略
4. **订单管理器** (`UserOrderManager`): 管理用户的订单操作
5. **事件处理器** (`EventHandler`): 处理系统事件
6. **日志管理器** (`LogManager`): 管理用户独立日志

### 状态控制

系统支持通过数据库直接控制监控状态：

1. **用户级别控制**：
```sql
-- 启用用户监控
UPDATE users SET status = 1 WHERE user_id = 'user123';

-- 禁用用户监控
UPDATE users SET status = 0 WHERE user_id = 'user123';
```

2. **策略级别控制**：
```sql
-- 启用策略
UPDATE strategies SET status = 1 WHERE strategy_id = 'strategy123';

-- 禁用策略
UPDATE strategies SET status = 0 WHERE strategy_id = 'strategy123';
```

3. **订单级别控制**：
```sql
-- 取消订单
UPDATE orders SET status = 'cancelled' WHERE order_id = 'order123';
```

### 日志管理

- **系统日志**: `logs/system.log`
- **用户日志**: `logs/users/user_{user_id}/user_{user_id}_{date}.log`
- **自动清理**: 保留最近7天的日志文件
- **日志级别**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### 监控功能

1. **实时监控**: 每10秒扫描一次用户状态
2. **健康检查**: 定期检查系统组件健康状态
3. **事件驱动**: 基于事件的异步处理机制
4. **高并发**: 支持多线程并发处理
5. **缓存优化**: Redis缓存提升性能

## 数据库表结构

详细的数据库表结构请参考 `framework/database/schema.sql` 文件，主要包括：

### 核心表

1. **users 表**: 用户基础信息表
   - 用户ID、状态、创建时间等
   - 支持用户级别的监控控制

2. **strategies 表**: 策略配置表
   - 策略ID、用户ID、策略类型、参数等
   - 支持策略级别的启用/禁用控制

3. **orders 表**: 订单详情表
   - 订单ID、用户ID、策略ID、订单状态等
   - 记录完整的订单生命周期

4. **order_logs 表**: 订单日志表
   - 记录订单状态变更历史
   - 支持审计和问题追踪

### 系统架构详解

#### 分层架构

```
┌─────────────────────────────────────┐
│           应用层 (app.py)            │
├─────────────────────────────────────┤
│         监控引擎层                   │
│  ┌─────────────┐ ┌─────────────┐    │
│  │MonitoringEngine│ │EventHandler │    │
│  └─────────────┘ └─────────────┘    │
├─────────────────────────────────────┤
│         业务逻辑层                   │
│  ┌─────────────┐ ┌─────────────┐    │
│  │UserMonitor  │ │StrategyMgr  │    │
│  └─────────────┘ └─────────────┘    │
│  ┌─────────────┐ ┌─────────────┐    │
│  │OrderManager │ │ LogManager  │    │
│  └─────────────┘ └─────────────┘    │
├─────────────────────────────────────┤
│         数据访问层                   │
│  ┌─────────────┐ ┌─────────────┐    │
│  │DatabasePool │ │ RedisPool   │    │
│  └─────────────┘ └─────────────┘    │
└─────────────────────────────────────┘
```

#### 核心组件

1. **MonitoringEngine**: 监控引擎
   - 管理所有用户监控器
   - 多线程并发处理
   - 健康检查和故障恢复

2. **UserMonitor**: 用户监控器
   - 监控单个用户的策略和订单
   - 策略执行和订单管理
   - 事件驱动的状态更新

3. **StrategyManager**: 策略管理器
   - 策略加载和执行
   - 策略状态管理
   - 策略参数配置

4. **UserOrderManager**: 订单管理器
   - 订单CRUD操作
   - 订单状态跟踪
   - 缓存优化

5. **EventHandler**: 事件处理器
   - 异步事件处理
   - 事件路由和分发
   - 线程池管理

6. **LogManager**: 日志管理器
   - 用户独立日志
   - 自动日志清理
   - 日志级别控制

#### 工作流程

1. **系统启动**：
   - 初始化数据库和Redis连接池
   - 启动日志管理器和事件处理器
   - 启动监控引擎和用户扫描

2. **用户监控**：
   - 扫描活跃用户
   - 为每个用户创建监控器
   - 加载用户策略和订单

3. **策略执行**：
   - 检查策略状态和条件
   - 执行策略逻辑
   - 生成和管理订单

4. **事件处理**：
   - 监听订单和策略事件
   - 异步处理事件响应
   - 更新状态和发送通知

## 性能优化

### 数据库优化
- **连接池管理**: 使用DBUtils连接池减少连接开销
- **批量操作**: 批量查询和更新提高处理效率
- **索引优化**: 为常用查询字段建立索引
- **分页查询**: 大数据量查询使用分页避免内存溢出

### 缓存优化
- **Redis缓存**: 缓存用户状态、策略配置等热点数据
- **本地缓存**: 使用内存缓存减少Redis访问
- **缓存策略**: 合理设置缓存过期时间和更新策略
- **缓存预热**: 系统启动时预加载关键数据

### 并发优化
- **多线程处理**: 使用ThreadPoolExecutor提高并发能力
- **异步处理**: 事件驱动的异步处理机制
- **负载均衡**: 用户监控器的动态负载分配
- **资源隔离**: 用户间资源隔离避免相互影响

### 内存优化
- **对象池**: 重用对象减少GC压力
- **内存监控**: 定期监控内存使用情况
- **资源清理**: 及时清理不再使用的资源
- **垃圾回收**: 优化GC参数提高性能

## 监控和运维

### 系统监控
- **组件状态**: 实时监控各组件运行状态
- **性能指标**: CPU、内存、网络等性能指标统计
- **业务指标**: 用户数量、订单处理量等业务指标
- **错误监控**: 异常和错误的实时监控和告警

### 日志管理
- **分级日志**: 支持DEBUG、INFO、WARNING、ERROR、CRITICAL级别
- **用户隔离**: 每个用户独立的日志文件
- **自动清理**: 7天自动清理机制
- **日志分析**: 支持日志查询和分析

### 运维工具
- **优雅关闭**: 支持SIGTERM信号的优雅关闭
- **状态查询**: 实时查询系统运行状态
- **健康检查**: 定期健康检查和自动恢复
- **配置热更新**: 支持部分配置的热更新

### 部署和扩展
- **容器化**: 支持Docker容器化部署
- **水平扩展**: 支持多实例部署和负载均衡
- **高可用**: 支持主备模式和故障转移
- **监控集成**: 支持Prometheus、Grafana等监控工具

## 故障排除

### 常见问题

1. **数据库连接失败**
   ```bash
   # 检查数据库连接
   python app.py test
   
   # 检查配置文件
   cat .env | grep MYSQL
   ```

2. **Redis连接失败**
   ```bash
   # 检查Redis服务
   redis-cli ping
   
   # 检查Redis配置
   cat .env | grep REDIS
   ```

3. **日志文件过多**
   ```bash
   # 手动清理日志
   python -c "from framework.logging import log_manager; log_manager.force_cleanup()"
   ```

4. **内存使用过高**
   ```bash
   # 查看系统状态
   python app.py status
   
   # 重启系统
   ./start.sh restart
   ```

### 调试模式

启用调试模式获取更详细的日志信息：

```bash
# 设置调试级别
export LOG_LEVEL=DEBUG

# 启动系统
python app.py start
```

### 性能分析

使用内置的性能分析工具：

```python
from framework.monitoring import monitoring_engine

# 获取性能统计
stats = monitoring_engine.get_stats()
print(f"活跃用户数: {stats['active_users']}")
print(f"处理事件数: {stats['processed_events']}")
```

## 贡献指南

欢迎贡献代码和提出改进建议！

### 开发环境设置

1. Fork 项目到你的GitHub账户
2. 克隆项目到本地
3. 创建开发分支
4. 安装开发依赖

```bash
pip install -r requirements.txt
```

### 代码规范

- 遵循PEP 8代码风格
- 添加适当的注释和文档字符串
- 编写单元测试
- 确保所有测试通过

### 提交流程

1. 创建功能分支
2. 提交代码变更
3. 编写测试用例
4. 提交Pull Request

## 许可证

本项目采用MIT许可证，详情请参阅LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交Issue: [GitHub Issues](https://github.com/your-repo/issues)
- 邮箱: your-email@example.com

## 更新日志

### v1.0.0 (2024-01-XX)
- 初始版本发布
- 实现高并发订单监控系统
- 支持用户独立日志系统
- 实现事件驱动架构
- 支持Redis缓存优化

---

**高并发订单监控系统** - 专业的实时订单监控解决方案
