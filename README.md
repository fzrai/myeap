# MyEAP - 企业级设备自动化控制系统

> Enterprise Equipment Automation Program for Semiconductor Manufacturing

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/fzrai/myeap?style=social)](https://github.com/fzrai/myeap/stargazers)
[![Build Status](https://img.shields.io/github/actions/workflow/status/fzrai/myeap/ci.yml)](https://github.com/fzrai/myeap/actions)

---

## 📖 目录 / Table of Contents

- [中文介绍](#中文介绍)
- [English Introduction](#english-introduction)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [功能列表 / Features](#功能列表--features)
- [架构设计 / Architecture](#架构设计--architecture)
- [技术栈 / Tech Stack](#技术栈--tech-stack)
- [项目结构 / Project Structure](#项目结构--project-structure)
- [开发指南 / Development](#开发指南--development)
- [贡献指南 / Contributing](#贡献指南--contributing)
- [许可证 / License](#许可证--license)

---

## 中文介绍

**MyEAP** 是一款面向半导体制造工厂的企业级设备自动化控制系统，完全符合SEMI标准，支持2000+设备的智能控制与管理。

### 核心能力

| 能力 | 描述 |
|------|------|
| **SECS/GEM协议** | 完全符合SEMI E5/E37标准，支持HSMS高速通信 |
| **MES集成** | 支持MQTT、REST API、Kafka多种方式与MES系统通信 |
| **设备控制** | 支持清洗、CVD、PVD、刻蚀、光刻、扩散、CMP等全类型设备 |
| **配方管理** | 配方版本控制、上传下载、审批流程、参数化模板 |
| **报警管理** | 多级报警、实时通知、自动升级、统计分析 |
| **数据采集** | 高频工艺数据采集、SPC分析、FDC故障检测 |
| **追踪追溯** | 载具管理、晶圆追踪、批次追溯、影响分析 |
| **AI智能** | 预测性维护、良率预测、根因分析 |
| **数字孪生** | 虚拟设备镜像、What-If仿真 |

### 目标场景

- ✅ 单Fab（50-2000台设备）
- ✅ 多Fab集中管理
- ✅ 8英寸/12英寸晶圆Fab
- ✅ 成熟制程/先进制程

---

## English Introduction

**MyEAP** is an enterprise-grade Equipment Automation Program designed for semiconductor manufacturing factories, fully compliant with SEMI standards, supporting intelligent control and management of 2000+ equipment.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **SECS/GEM Protocol** | Fully compliant with SEMI E5/E37, HSMS high-speed communication |
| **MES Integration** | MQTT, REST API, Kafka integration with MES systems |
| **Equipment Control** | Support for Cleaner, CVD, PVD, Etcher, Lithography, Diffusion, CMP and more |
| **Recipe Management** | Version control, upload/download, approval workflow, parameterized templates |
| **Alarm Management** | Multi-level alarms, real-time notifications, auto-escalation, statistics |
| **Data Collection** | High-frequency process data, SPC analysis, FDC fault detection |
| **Tracking & Traceability** | Carrier management, wafer tracking, lot traceability, impact analysis |
| **AI Intelligence** | Predictive maintenance, yield prediction, root cause analysis |
| **Digital Twin** | Virtual equipment mirror, What-If simulation |

---

## 快速开始 / Quick Start

### 环境要求 / Requirements

- Python 3.11+
- Docker & Docker Compose (开发/Development)
- Kubernetes 1.28+ (生产/Production)

### 安装 / Installation

```bash
# 克隆仓库 / Clone repository
git clone https://github.com/fzrai/myeap.git
cd myeap

# 安装依赖 / Install dependencies
uv sync

# 运行测试 / Run tests
uv run pytest

# 启动开发服务器 / Start dev server
uv run uvicorn myeap.api.main:app --reload
```

### Docker部署 / Docker Deployment

```bash
# 启动所有服务 / Start all services
docker-compose up -d

# 查看日志 / View logs
docker-compose logs -f api

# 停止服务 / Stop services
docker-compose down
```

### Kubernetes部署 / Kubernetes Deployment

```bash
# 部署到K8s / Deploy to K8s
kubectl apply -f configs/k8s/

# 查看Pod状态 / Check pod status
kubectl get pods -n myeap
```

---

## 功能列表 / Features

### 1. SECS/GEM协议层 / SECS/GEM Protocol Layer

| 功能 Feature | 描述 Description |
|-------------|------------------|
| SECS-II消息编解码 | SECS-II message encoding/decoding |
| HSMS连接管理 | HSMS connection management |
| GEM状态机 | GEM state machine (SEMI E30) |
| 标准消息处理 | Standard message handling (S1-S15) |
| 自动重连 | Auto reconnection with exponential backoff |
| 消息追踪 | Message tracing and logging |

### 2. MES集成层 / MES Integration Layer

| 功能 Feature | 描述 Description |
|-------------|------------------|
| MQTT适配器 | MQTT adapter for pub/sub messaging |
| REST适配器 | REST API adapter for HTTP communication |
| Kafka适配器 | Kafka adapter for event streaming |
| 工单接收 | Work order reception |
| 状态上报 | Equipment status reporting |
| 报警上报 | Alarm reporting |
| 产量上报 | Throughput reporting |

### 3. 设备控制层 / Device Control Layer

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 设备抽象 | Equipment abstraction |
| 腔体控制 | Chamber control |
| 工艺控制 | Process control |
| 设备插件系统 | Plugin system for equipment types |
| 清洗设备插件 | Cleaner equipment plugin |
| CVD设备插件 | CVD equipment plugin |

### 4. 配方管理 / Recipe Management

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 配方CRUD | Recipe CRUD operations |
| 版本控制 | Semantic version control (X.Y.Z) |
| 审批流程 | Approval workflow |
| 上传下载 | Upload/download to equipment |
| 配方比对 | Recipe comparison |
| 参数化模板 | Parameterized recipe templates |
| 配方验证 | Recipe validation rules |

### 5. 报警管理 / Alarm Management

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 报警检测 | Alarm detection |
| 报警分级 | Alarm severity (CRITICAL/MAJOR/MINOR/WARNING) |
| 报警通知 | Multi-channel notifications (Email/SMS/Webhook) |
| 报警升级 | Auto-escalation |
| 报警确认 | Alarm acknowledgment |
| 报警屏蔽 | Alarm suppression |
| 统计分析 | Alarm statistics and patterns |

### 6. 数据采集 / Data Collection

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 实时采集 | Real-time data collection |
| 定时采样 | Time-based sampling |
| 变化采样 | Change-based sampling |
| 统计采样 | Statistical sampling (aggregation) |
| 智能采样 | Smart sampling based on signal features |
| 限值监控 | Limit monitoring (UCL/LCL/USL/LSL) |

### 7. SPC/FDC引擎

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 控制图 | Control charts (X-bar, R, S, X-MR, C, U, P, NP) |
| SPC规则 | SPC rules (Westgard rules) |
| 过程能力 | Process capability (Cp, Cpk, Pp, Ppk) |
| FDC检测 | Fault detection and classification |
| 特征提取 | Feature extraction |
| 异常检测 | Anomaly detection algorithms |

### 8. 追踪服务 / Tracking Service

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 载具注册 | Carrier registration (FOUP, FOSB) |
| 载具追踪 | Carrier tracking |
| 晶圆追踪 | Wafer tracking |
| 腔体映射 | Chamber mapping |
| 追溯查询 | Traceability queries |
| 影响分析 | Impact analysis |
| 正向追踪 | Forward traceability |
| 反向追溯 | Backward traceability |

### 9. AI/ML模块

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 预测性维护 | Predictive maintenance |
| 良率预测 | Yield prediction |
| 根因分析 | Root cause analysis |
| 时序预测 | Time series forecasting |
| 异常检测 | Anomaly detection |

### 10. 可观测性 / Observability

| 功能 Feature | 描述 Description |
|-------------|------------------|
| Prometheus指标 | Prometheus metrics |
| OpenTelemetry追踪 | Distributed tracing |
| 结构化日志 | Structured logging |
| 健康检查 | Health checks (Liveness/Readiness) |
| 告警聚合 | Alert aggregation |

### 11. 安全与合规 / Security & Compliance

| 功能 Feature | 描述 Description |
|-------------|------------------|
| 认证授权 | Authentication & Authorization |
| RBAC权限 | Role-based access control |
| 操作审计 | Operation audit trail |
| 电子签名 | Electronic signature (21 CFR Part 11) |
| 数据加密 | Data encryption |

---

## 架构设计 / Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster (多可用区)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Ingress Layer                               │   │
│  │                    (Nginx Ingress + SSL Termination)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       MES Integration Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │   MQTT      │  │   REST      │  │   Kafka     │  │  Config     │  │   │
│  │  │   Adapter   │  │   Gateway   │  │  Consumer   │  │  Registry   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Shared Services Layer                            │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐   │   │
│  │  │  Recipe   │ │  Alarm    │ │  Data     │ │       Audit         │   │   │
│  │  │  Manager  │ │  Handler  │ │ Collector │ │       Logger        │   │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────────┘   │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐   │   │
│  │  │   SPC     │ │   FDC     │ │ Digital   │ │    Predictive       │   │   │
│  │  │  Engine   │ │  Engine   │ │   Twin    │ │    Maintenance     │   │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Device Control Layer                            │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐     │   │
│  │  │              Device Supervisor (每设备一个Pod)                 │     │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐     │     │   │
│  │  │  │   SECS/GEM  │  │  Equipment   │  │    Process      │     │     │   │
│  │  │  │   Driver    │  │    State     │  │   Controller    │     │     │   │
│  │  │  │  (pycomm3)  │  │   Machine    │  │                 │     │     │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────┘     │     │   │
│  │  └─────────────────────────────────────────────────────────────┘     │   │
│  │                                                                       │   │
│  │  [Cleaner] [CVD] [PVD] [Etcher] [Lithography] [Diffusion] [CMP]   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Data Layer                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────┐  │   │
│  │  │    Redis     │  │  PostgreSQL  │  │  TimescaleDB │  │ MinIO │  │   │
│  │  │   Cluster    │  │   (Citus)    │  │  (时序数据)   │  │ (S3)  │  │   │
│  │  │ (状态/缓存)  │  │  (事务/历史)  │  │   (FDC/SPC)  │  │(配方) │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 技术栈 / Tech Stack

| 类别 Category | 技术 Technology |
|--------------|-----------------|
| **语言** Language | Python 3.11+ |
| **异步框架** Async | asyncio, FastAPI, uvicorn |
| **协议** Protocol | pycomm3 (SECS/GEM/HSMS) |
| **消息队列** Messaging | Apache Kafka, MQTT |
| **数据库** Database | PostgreSQL, Redis, TimescaleDB |
| **对象存储** Storage | MinIO (S3-compatible) |
| **容器化** Container | Docker, Kubernetes |
| **监控** Monitoring | Prometheus, Grafana, Jaeger |
| **AI/ML** | PyTorch, scikit-learn, statsmodels |
| **安全** Security | OAuth2, JWT, LDAP |

---

## 项目结构 / Project Structure

```
myeap/
├── src/myeap/                    # 源代码 / Source code
│   ├── core/                     # 核心基础设施 / Core infrastructure
│   │   ├── config.py             # 配置管理 / Configuration
│   │   ├── logging.py           # 结构化日志 / Structured logging
│   │   └── exceptions.py        # 异常定义 / Exception definitions
│   │
│   ├── observability/            # 可观测性 / Observability
│   │   ├── metrics.py           # Prometheus指标 / Metrics
│   │   ├── tracing.py           # 分布式追踪 / Tracing
│   │   └── health.py            # 健康检查 / Health checks
│   │
│   ├── db/                       # 数据库层 / Database layer
│   │   ├── models.py            # SQLAlchemy模型 / ORM models
│   │   └── session.py            # 异步会话 / Async sessions
│   │
│   ├── secs/                     # SECS/GEM协议层 / Protocol layer
│   │   ├── protocol/            # SECS-II协议 / SECS-II protocol
│   │   │   ├── message.py       # 消息定义 / Message definitions
│   │   │   ├── codec.py         # 编解码器 / Encoder/decoder
│   │   │   └── hsms.py          # HSMS连接 / HSMS connection
│   │   │
│   │   └── gem/                 # GEM标准 / GEM standard
│   │       ├── handler.py       # 消息处理 / Message handlers
│   │       ├── state_machine.py # 状态机 / State machine
│   │       └── messages.py      # 标准消息 / Standard messages
│   │
│   ├── mes/                      # MES集成层 / MES integration
│   │   └── adapters/            # 适配器 / Adapters
│   │       ├── base.py          # 基类 / Base class
│   │       ├── mqtt.py          # MQTT / MQTT adapter
│   │       ├── rest.py          # REST / REST adapter
│   │       └── kafka.py         # Kafka / Kafka adapter
│   │
│   ├── device/                  # 设备控制层 / Device control
│   │   ├── equipment.py         # 设备抽象 / Equipment abstraction
│   │   ├── chamber.py           # 腔体控制 / Chamber control
│   │   ├── process.py          # 工艺控制 / Process control
│   │   ├── registry.py         # 设备注册表 / Registry
│   │   └── plugins/             # 设备插件 / Equipment plugins
│   │       ├── base.py          # 插件基类 / Plugin base
│   │       ├── cleaner.py       # 清洗设备 / Cleaner
│   │       └── cvd.py           # CVD设备 / CVD
│   │
│   ├── recipe/                   # 配方管理 / Recipe management
│   │   ├── models.py           # 配方模型 / Recipe models
│   │   ├── manager.py          # 配方服务 / Recipe service
│   │   ├── validator.py        # 配方验证 / Recipe validation
│   │   └── version_control.py    # 版本控制 / Version control
│   │
│   ├── alarm/                    # 报警管理 / Alarm management
│   │   ├── models.py           # 报警模型 / Alarm models
│   │   ├── manager.py          # 报警服务 / Alarm service
│   │   ├── escalation.py       # 报警升级 / Alarm escalation
│   │   └── notifier.py         # 报警通知 / Alarm notification
│   │
│   ├── tracking/                 # 追踪服务 / Tracking service
│   │   ├── models.py           # 追踪模型 / Tracking models
│   │   ├── carrier.py          # 载具管理 / Carrier management
│   │   ├── wafer.py            # 晶圆追踪 / Wafer tracking
│   │   └── service.py          # 追溯服务 / Traceability
│   │
│   ├── data/                     # 数据采集 / Data collection
│   │   ├── collector.py        # 采集器 / Collector
│   │   ├── storage.py          # 数据存储 / Data storage
│   │   ├── sampler.py          # 采样器 / Sampler
│   │   └── limit_monitor.py    # 限值监控 / Limit monitoring
│   │
│   ├── spc/                      # SPC引擎 / SPC engine
│   │   ├── charts.py           # 控制图 / Control charts
│   │   ├── rules.py            # SPC规则 / SPC rules
│   │   └── capability.py        # 过程能力 / Process capability
│   │
│   ├── fdc/                      # FDC引擎 / FDC engine
│   │   ├── detector.py         # 故障检测 / Fault detection
│   │   ├── classifier.py        # 故障分类 / Fault classification
│   │   └── features.py         # 特征提取 / Feature extraction
│   │
│   ├── ai/                       # AI/ML模块 / AI/ML module
│   │   ├── predictive_maintenance.py  # 预测性维护
│   │   ├── yield_prediction.py         # 良率预测
│   │   └── root_cause.py             # 根因分析
│   │
│   ├── twin/                     # 数字孪生 / Digital twin
│   │   ├── digital_twin.py     # 数字孪生 / Digital twin
│   │   └── simulation.py       # 仿真模拟 / Simulation
│   │
│   ├── security/                 # 安全服务 / Security
│   │   ├── auth.py             # 认证授权 / Auth
│   │   ├── rbac.py             # 权限控制 / RBAC
│   │   └── audit.py            # 审计日志 / Audit
│   │
│   └── api/                     # REST API
│       └── main.py              # API入口 / API entry
│
├── tests/                         # 测试 / Tests
│   ├── unit/                    # 单元测试 / Unit tests
│   └── integration/            # 集成测试 / Integration tests
│
├── configs/                      # 配置文件 / Config files
│   ├── k8s/                    # Kubernetes配置
│   └── docker/                 # Docker配置
│
├── docs/                         # 文档 / Documentation
│   ├── user/                   # 用户文档 / User docs
│   ├── developer/              # 开发者文档 / Developer docs
│   ├── api/                    # API文档 / API docs
│   └── specs/                  # 设计规范 / Specifications
│
├── alembic/                      # 数据库迁移 / DB migrations
├── docker-compose.yml           # Docker Compose (生产)
├── docker-compose.dev.yml       # Docker Compose (开发)
├── Dockerfile                   # Docker镜像
├── pyproject.toml              # 项目配置
├── mkdocs.yml                  # 文档配置
├── README.md                   # 本文件
└── LICENSE                    # MIT许可证
```

---

## 开发指南 / Development

### 代码规范 / Code Standards

```bash
# 代码格式化 / Format code
uv run black .

# 导入排序 / Sort imports
uv run isort .

# 代码检查 / Lint code
uv run ruff check .

# 类型检查 / Type check
uv run mypy src/
```

### 测试 / Testing

```bash
# 运行所有测试 / Run all tests
uv run pytest

# 带覆盖率 / With coverage
uv run pytest --cov=myeap --cov-report=html --cov-report=term

# 特定模块 / Specific module
uv run pytest tests/unit/secs/
uv run pytest tests/unit/mes/
uv run pytest tests/unit/device/
```

### 提交规范 / Commit Convention

```
feat:     新功能 / New feature
fix:      修复bug / Bug fix
docs:     文档更新 / Documentation
style:    代码格式 / Code style
refactor: 重构 / Refactoring
test:     测试 / Tests
chore:    构建/工具 / Build/Tools
```

---

## 贡献指南 / Contributing

1. Fork本仓库 / Fork this repository
2. 创建特性分支 / Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. 提交更改 / Commit your changes (`git commit -m 'feat: Add AmazingFeature'`)
4. 推送到分支 / Push to the branch (`git push origin feature/AmazingFeature`)
5. 创建Pull Request / Create a Pull Request

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

This project is open source under the [MIT License](LICENSE).

---

<p align="center">
  <strong>Made with ❤️ for Semiconductor Manufacturing</strong>
  <br>
  为半导体制造而生
</p>
