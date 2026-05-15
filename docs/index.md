# MyEAP - Enterprise Equipment Automation Program

> 面向半导体制造的企业级设备自动化控制系统

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-blue)](https://myeap.example.com/docs)

## 核心特性

### 全面SECS/GEM支持
完全符合SEMI E5/E37标准，支持HSMS高速通信协议，与各类半导体设备无缝对接。

### 智能工艺控制
实时工艺监控、自适应参数调整、端到端批次追踪，确保工艺稳定性。

### SPC/FDC集成
内置统计过程控制和故障检测分类系统，实时预警工艺异常。

### AI驱动的分析
预测性维护、良率预测、根因分析，基于历史数据持续优化生产效率。

### 数字孪生
虚拟设备镜像、What-If仿真分析，在虚拟环境中预验证工艺变更。

### 高可用架构
Kubernetes原生设计，支持故障自动转移、滚动升级，确保生产连续性。

## 架构

MyEAP采用微服务架构，将系统划分为多个独立的服务层：

```
┌─────────────────────────────────────────────────────────────┐
│                    MES Integration Layer                     │
│           (MQTT / REST / Kafka 适配器)                    │
├─────────────────────────────────────────────────────────────┤
│                    Shared Services Layer                     │
│     (配方 | 报警 | SPC | FDC | 追踪 | 审计 | 安全)        │
├─────────────────────────────────────────────────────────────┤
│                    Device Control Layer                     │
│              (SECS/GEM 驱动 + 工艺控制)                    │
├─────────────────────────────────────────────────────────────┤
│                      Data Layer                             │
│     (PostgreSQL | Redis | Kafka | TimescaleDB | MinIO)     │
└─────────────────────────────────────────────────────────────┘
```

## 快速链接

- [用户文档](user/) - 系统使用指南
- [开发者文档](developer/) - 开发指南和架构说明
- [API参考](api/) - REST API接口文档
- [设计规范](specs/) - 详细技术规范

## 版本信息

当前版本: **0.1.0** (开发中)

许可证: [MIT](LICENSE)
