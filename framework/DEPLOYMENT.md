# 高并发订单监控系统 - 部署指南

## 目录
- [系统要求](#系统要求)
- [环境准备](#环境准备)
- [安装部署](#安装部署)
- [配置说明](#配置说明)
- [启动和停止](#启动和停止)
- [监控和维护](#监控和维护)
- [故障排除](#故障排除)
- [性能优化](#性能优化)
- [安全配置](#安全配置)

## 系统要求

### 硬件要求

#### 最低配置
- CPU: 4核心 2.0GHz
- 内存: 8GB RAM
- 存储: 100GB SSD
- 网络: 100Mbps

#### 推荐配置
- CPU: 8核心 3.0GHz
- 内存: 16GB RAM
- 存储: 500GB NVMe SSD
- 网络: 1Gbps

#### 生产环境配置
- CPU: 16核心 3.5GHz
- 内存: 32GB RAM
- 存储: 1TB NVMe SSD (系统) + 2TB SSD (数据)
- 网络: 10Gbps

### 软件要求

#### 操作系统
- **Linux**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- **Windows**: Windows Server 2019+ / Windows 10+
- **macOS**: macOS 11.0+

#### 依赖软件
- **Python**: 3.7+ (推荐 3.9+)
- **MySQL**: 5.7+ (推荐 8.0+)
- **Redis**: 5.0+ (推荐 6.2+)
- **Git**: 2.20+

## 环境准备

### 1. 安装Python环境

#### Linux/macOS
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip

# macOS (使用Homebrew)
brew install python@3.9
```

#### Windows
1. 从 [Python官网](https://www.python.org/downloads/) 下载Python 3.9+
2. 安装时勾选 "Add Python to PATH"
3. 验证安装：
```cmd
python --version
pip --version
```

### 2. 安装MySQL数据库

#### Linux
```bash
# Ubuntu/Debian
sudo apt install mysql-server mysql-client

# CentOS/RHEL
sudo yum install mysql-server mysql

# 启动MySQL服务
sudo systemctl start mysql
sudo systemctl enable mysql

# 安全配置
sudo mysql_secure_installation
```

#### Windows
1. 从 [MySQL官网](https://dev.mysql.com/downloads/mysql/) 下载MySQL Installer
2. 选择 "Developer Default" 安装类型
3. 设置root密码
4. 启动MySQL服务

#### macOS
```bash
# 使用Homebrew
brew install mysql

# 启动MySQL服务
brew services start mysql

# 安全配置
mysql_secure_installation
```

### 3. 安装Redis缓存

#### Linux
```bash
# Ubuntu/Debian
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis

# 启动Redis服务
sudo systemctl start redis
sudo systemctl enable redis
```

#### Windows
1. 从 [Redis官网](https://redis.io/download) 下载Windows版本
2. 解压到指定目录
3. 运行 `redis-server.exe`

#### macOS
```bash
# 使用Homebrew
brew install redis

# 启动Redis服务
brew services start redis
```

## 安装部署

### 1. 获取源代码

```bash
# 克隆代码仓库
git clone <repository-url>
cd dbaa

# 或者下载压缩包并解压
wget <download-url>
unzip dbaa.zip
cd dbaa
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. 安装依赖

```bash
# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证安装
pip list
```

### 4. 数据库初始化

#### 创建数据库
```sql
-- 连接到MySQL
mysql -u root -p

-- 创建数据库
CREATE DATABASE order_monitor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（可选）
CREATE USER 'order_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON order_monitor.* TO 'order_user'@'localhost';
FLUSH PRIVILEGES;

-- 退出MySQL
EXIT;
```

#### 导入表结构
```bash
# 导入数据库表结构
mysql -u root -p order_monitor < framework/database/schema.sql

# 验证表创建
mysql -u root -p order_monitor -e "SHOW TABLES;"
```

### 5. 配置Redis

#### 编辑Redis配置文件
```bash
# Linux
sudo nano /etc/redis/redis.conf

# 关键配置项
bind 127.0.0.1
port 6379
requirepass your_redis_password
maxmemory 2gb
maxmemory-policy allkeys-lru
```

#### 重启Redis服务
```bash
# Linux
sudo systemctl restart redis

# 验证Redis连接
redis-cli ping
```

## 配置说明

### 1. 环境配置文件

创建 `.env` 文件：

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

### 2. 数据库配置

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_NAME=order_monitor
DB_USER=order_user
DB_PASSWORD=secure_password
DB_CHARSET=utf8mb4

# 连接池配置
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### 3. Redis配置

```env
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# 连接池配置
REDIS_POOL_SIZE=20
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
```

### 4. 日志配置

```env
# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=detailed
LOG_FILE_SIZE=100MB
LOG_BACKUP_COUNT=10
LOG_ROTATION=daily

# 日志路径
LOG_DIR=logs
SYSTEM_LOG_FILE=system.log
USER_LOG_FILE=user.log
ERROR_LOG_FILE=error.log
```

### 5. 监控配置

```env
# 监控配置
MONITOR_ENABLED=true
MONITOR_INTERVAL=5
HEALTH_CHECK_INTERVAL=30
METRICS_RETENTION_DAYS=30

# 性能配置
MAX_CONCURRENT_ORDERS=10000
ORDER_PROCESSING_TIMEOUT=30
CACHE_TTL=3600
BATCH_SIZE=1000
```

### 6. 安全配置

```env
# 安全配置
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here
API_RATE_LIMIT=1000
SESSION_TIMEOUT=3600

# 加密配置
ENCRYPTION_ALGORITHM=AES-256-GCM
PASSWORD_HASH_ROUNDS=12
```

## 启动和停止

### 1. 使用启动脚本（推荐）

#### Linux/macOS
```bash
# 启动系统
./start.sh

# 停止系统
./stop.sh

# 重启系统
./restart.sh

# 查看状态
./status.sh
```

#### Windows
```cmd
# 启动系统
start.bat

# 停止系统
stop.bat

# 重启系统
restart.bat

# 查看状态
status.bat
```

### 2. 手动启动

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 启动应用
python app.py

# 后台运行（Linux/macOS）
nohup python app.py > logs/app.log 2>&1 &

# 查看进程
ps aux | grep app.py
```

### 3. 系统服务配置

#### Linux Systemd服务

创建服务文件 `/etc/systemd/system/order-monitor.service`：

```ini
[Unit]
Description=High Concurrency Order Monitoring System
After=network.target mysql.service redis.service

[Service]
Type=simple
User=order_user
Group=order_user
WorkingDirectory=/opt/order-monitor
Environment=PATH=/opt/order-monitor/.venv/bin
ExecStart=/opt/order-monitor/.venv/bin/python app.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable order-monitor
sudo systemctl start order-monitor
sudo systemctl status order-monitor
```

#### Windows服务

使用 `pywin32` 创建Windows服务：

```python
# service.py
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os

class OrderMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OrderMonitorService"
    _svc_display_name_ = "Order Monitoring System"
    _svc_description_ = "High Concurrency Order Monitoring System"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        # 启动应用逻辑
        import app
        app.main()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(OrderMonitorService)
```

安装服务：
```cmd
python service.py install
python service.py start
```

## 监控和维护

### 1. 系统监控

#### 健康检查
```bash
# 检查系统状态
curl http://localhost:8000/health

# 检查数据库连接
python -c "from framework.database.connection import DatabaseManager; print(DatabaseManager().test_connection())"

# 检查Redis连接
redis-cli ping
```

#### 性能监控
```bash
# 查看系统资源使用
top
htop
iostat -x 1

# 查看网络连接
netstat -an | grep :8000

# 查看日志
tail -f logs/system.log
tail -f logs/error.log
```

### 2. 日志管理

#### 日志轮转配置
```bash
# 创建logrotate配置
sudo nano /etc/logrotate.d/order-monitor

# 配置内容
/opt/order-monitor/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 order_user order_user
    postrotate
        systemctl reload order-monitor
    endscript
}
```

#### 日志分析
```bash
# 错误日志分析
grep "ERROR" logs/system.log | tail -20

# 性能日志分析
grep "PERFORMANCE" logs/system.log | tail -20

# 统计请求量
grep "REQUEST" logs/system.log | wc -l
```

### 3. 数据库维护

#### 定期备份
```bash
# 创建备份脚本
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups"
DB_NAME="order_monitor"

mkdir -p $BACKUP_DIR

# 数据库备份
mysqldump -u root -p$DB_PASSWORD $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# 压缩备份
gzip $BACKUP_DIR/db_backup_$DATE.sql

# 删除7天前的备份
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/db_backup_$DATE.sql.gz"
EOF

chmod +x backup.sh
```

#### 性能优化
```sql
-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'long_query_time';

-- 分析表
ANALYZE TABLE orders;
ANALYZE TABLE users;
ANALYZE TABLE strategies;

-- 优化表
OPTIMIZE TABLE orders;
```

### 4. Redis维护

#### 内存监控
```bash
# 查看Redis内存使用
redis-cli info memory

# 查看键空间信息
redis-cli info keyspace

# 查看慢查询
redis-cli slowlog get 10
```

#### 数据清理
```bash
# 清理过期键
redis-cli --scan --pattern "temp:*" | xargs redis-cli del

# 手动触发内存清理
redis-cli memory purge
```

## 故障排除

### 1. 常见问题

#### 应用启动失败
```bash
# 检查端口占用
netstat -an | grep :8000
lsof -i :8000

# 检查权限
ls -la app.py
chmod +x app.py

# 检查依赖
pip check
pip list --outdated
```

#### 数据库连接失败
```bash
# 检查MySQL服务状态
systemctl status mysql

# 检查网络连接
telnet localhost 3306

# 检查用户权限
mysql -u order_user -p -e "SELECT USER(), DATABASE();"

# 检查配置
grep -E "DB_|MYSQL" .env
```

#### Redis连接失败
```bash
# 检查Redis服务状态
systemctl status redis

# 检查网络连接
telnet localhost 6379

# 检查认证
redis-cli auth your_password

# 检查配置
grep -E "REDIS" .env
```

### 2. 性能问题

#### 高CPU使用率
```bash
# 查看进程CPU使用
top -p $(pgrep -f app.py)

# 分析Python性能
python -m cProfile -o profile.stats app.py

# 查看系统调用
strace -p $(pgrep -f app.py)
```

#### 高内存使用
```bash
# 查看内存使用详情
ps aux | grep app.py
pmap $(pgrep -f app.py)

# Python内存分析
pip install memory_profiler
python -m memory_profiler app.py
```

#### 数据库性能问题
```sql
-- 查看正在运行的查询
SHOW PROCESSLIST;

-- 查看慢查询日志
SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;

-- 查看表锁情况
SHOW OPEN TABLES WHERE In_use > 0;
```

### 3. 错误处理

#### 应用错误
```bash
# 查看错误日志
tail -f logs/error.log

# 查看系统日志
journalctl -u order-monitor -f

# 调试模式运行
DEBUG=true python app.py
```

#### 网络错误
```bash
# 检查防火墙
sudo ufw status
sudo iptables -L

# 检查DNS解析
nslookup localhost
dig localhost

# 网络连通性测试
ping localhost
curl -I http://localhost:8000
```

## 性能优化

### 1. 应用层优化

#### 代码优化
- 使用连接池管理数据库连接
- 实现缓存策略减少数据库查询
- 优化算法和数据结构
- 使用异步处理提高并发性能

#### 配置优化
```env
# 增加工作进程数
WORKER_PROCESSES=8

# 调整连接池大小
DB_POOL_SIZE=50
REDIS_POOL_SIZE=50

# 优化缓存配置
CACHE_TTL=7200
CACHE_MAX_SIZE=1000000
```

### 2. 数据库优化

#### MySQL配置优化
```ini
# /etc/mysql/mysql.conf.d/mysqld.cnf
[mysqld]
# 内存配置
innodb_buffer_pool_size = 8G
innodb_log_file_size = 1G
innodb_log_buffer_size = 64M

# 连接配置
max_connections = 1000
max_connect_errors = 100000

# 查询缓存
query_cache_type = 1
query_cache_size = 256M

# 临时表
tmp_table_size = 256M
max_heap_table_size = 256M
```

#### 索引优化
```sql
-- 创建复合索引
CREATE INDEX idx_user_status_time ON orders(user_id, status, created_at);
CREATE INDEX idx_strategy_symbol ON orders(strategy_id, symbol);

-- 分析索引使用情况
EXPLAIN SELECT * FROM orders WHERE user_id = 'user001' AND status = 'pending';
```

### 3. Redis优化

#### 配置优化
```conf
# redis.conf
# 内存配置
maxmemory 4gb
maxmemory-policy allkeys-lru

# 持久化配置
save 900 1
save 300 10
save 60 10000

# 网络配置
tcp-keepalive 300
timeout 0
```

#### 数据结构优化
- 使用Hash存储对象数据
- 使用Set存储唯一值集合
- 使用Sorted Set实现排行榜
- 合理设置过期时间

### 4. 系统级优化

#### 操作系统优化
```bash
# 调整文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 调整网络参数
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
sysctl -p
```

#### 硬件优化
- 使用SSD存储提高I/O性能
- 增加内存减少磁盘交换
- 使用多核CPU提高并发处理能力
- 配置高速网络连接

## 安全配置

### 1. 网络安全

#### 防火墙配置
```bash
# Ubuntu/Debian
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw deny 3306/tcp
sudo ufw deny 6379/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

#### SSL/TLS配置
```bash
# 生成SSL证书
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# 配置HTTPS
# 在应用配置中启用SSL
SSL_ENABLED=true
SSL_CERT_FILE=cert.pem
SSL_KEY_FILE=key.pem
```

### 2. 数据库安全

#### MySQL安全配置
```sql
-- 删除匿名用户
DELETE FROM mysql.user WHERE User='';

-- 删除测试数据库
DROP DATABASE IF EXISTS test;

-- 限制root用户远程登录
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');

-- 刷新权限
FLUSH PRIVILEGES;
```

#### 数据加密
```env
# 启用数据加密
DATA_ENCRYPTION_ENABLED=true
ENCRYPTION_KEY=your_32_character_encryption_key

# 敏感数据脱敏
MASK_SENSITIVE_DATA=true
LOG_SENSITIVE_DATA=false
```

### 3. 应用安全

#### 访问控制
```env
# API认证
API_AUTH_ENABLED=true
JWT_EXPIRATION=3600
REFRESH_TOKEN_EXPIRATION=86400

# 访问限制
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# IP白名单
IP_WHITELIST_ENABLED=true
ALLOWED_IPS=127.0.0.1,192.168.1.0/24
```

#### 日志安全
```env
# 审计日志
AUDIT_LOG_ENABLED=true
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_RETENTION=90

# 敏感信息过滤
LOG_FILTER_PASSWORDS=true
LOG_FILTER_TOKENS=true
LOG_FILTER_PERSONAL_DATA=true
```

### 4. 运维安全

#### 定期安全检查
```bash
# 系统更新
sudo apt update && sudo apt upgrade  # Ubuntu/Debian
sudo yum update                       # CentOS/RHEL

# 安全扫描
sudo apt install lynis
sudo lynis audit system

# 漏洞检查
sudo apt install chkrootkit
sudo chkrootkit
```

#### 备份安全
```bash
# 加密备份
gpg --cipher-algo AES256 --compress-algo 1 --s2k-cipher-algo AES256 \
    --s2k-digest-algo SHA512 --s2k-mode 3 --s2k-count 65536 \
    --symmetric backup.sql

# 异地备份
rsync -avz --delete /opt/backups/ user@backup-server:/backups/
```

---

## 总结

本部署指南涵盖了高并发订单监控系统的完整部署流程，包括：

1. **环境准备**: 系统要求、软件安装
2. **安装配置**: 代码部署、数据库初始化、配置文件设置
3. **启动运行**: 多种启动方式、系统服务配置
4. **监控维护**: 健康检查、日志管理、定期维护
5. **故障排除**: 常见问题解决方案
6. **性能优化**: 应用、数据库、系统级优化
7. **安全配置**: 网络、数据、应用安全

请根据实际环境和需求调整相关配置，确保系统稳定、安全、高效运行。

如有问题，请参考故障排除章节或联系技术支持团队。