# 架构设计

## 整体架构

MyEAP采用微服务架构，分为以下几层：

### 1. MES Integration Layer

负责与MES系统通信：

- **MQTT Adapter**: 订阅工单主题，发布设备事件
- **REST Gateway**: 提供设备状态查询、远程控制API
- **Kafka Consumer**: 消费MES消息队列

### 2. Shared Services Layer

公共业务服务：

- **Recipe Manager**: 配方存储与版本管理
- **Alarm Handler**: 报警检测与通知
- **Data Collector**: 高频数据采集
- **Audit Logger**: 操作审计

### 3. Device Control Layer

设备控制层：

- **SECS/GEM Driver**: SECS协议通信
- **Equipment State Machine**: 设备状态机
- **Process Controller**: 工艺流程控制

### 4. Data Layer

数据存储层：

- **PostgreSQL**: 事务数据存储
- **Redis**: 缓存与实时状态
- **Kafka**: 消息队列
- **TimescaleDB**: 时序数据

## 核心技术栈

- **语言**: Python 3.11+
- **框架**: FastAPI, asyncio
- **数据库**: PostgreSQL, Redis
- **消息队列**: Apache Kafka
- **容器化**: Docker, Kubernetes

## 设计原则

1. **高可用**: 支持故障自动转移
2. **可扩展**: 水平扩展能力
3. **可观测**: 完整日志和监控
4. **安全**: 端到端加密和认证
