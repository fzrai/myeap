# 配置指南

详细说明MyEAP系统的配置选项。

## 环境变量

### 数据库配置

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `DB_HOST` | localhost | PostgreSQL主机 |
| `DB_PORT` | 5432 | PostgreSQL端口 |
| `DB_NAME` | myeap | 数据库名 |
| `DB_USER` | myeap | 数据库用户 |
| `DB_PASSWORD` | - | 数据库密码 |

### Redis配置

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `REDIS_HOST` | localhost | Redis主机 |
| `REDIS_PORT` | 6379 | Redis端口 |
| `REDIS_PASSWORD` | - | Redis密码 |

### MES集成配置

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `MES_MQTT_BROKER` | localhost:1883 | MQTT broker地址 |
| `MES_REST_ENDPOINT` | http://localhost:8001 | MES REST端点 |

### SECS/GEM配置

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `SECS_DEFAULT_TIMEOUT` | 10 | 默认超时时间(秒) |
| `SECS_RECONNECT_INTERVAL` | 5 | 重连间隔(秒) |

## 配置文件

系统也支持通过配置文件进行配置：

```yaml
# config.yaml
database:
  host: localhost
  port: 5432
  name: myeap

redis:
  host: localhost
  port: 6379

kafka:
  bootstrap_servers: localhost:9092
```

## 生产环境配置

生产环境建议：

1. 使用外部数据库服务
2. 配置SSL连接
3. 设置强密码
4. 启用日志持久化
