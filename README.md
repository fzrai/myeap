# MyEAP - Enterprise Equipment Automation Program

> 面向半导体制造的企业级设备自动化控制系统

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-blue)](https://myeap.example.com/docs)

## 特性

- **全面SECS/GEM支持**: 完全符合SEMI标准，支持HSMS通信
- **智能工艺控制**: 实时工艺监控、自适应参数调整
- **SPC/FDC集成**: 内置统计过程控制和故障检测分类
- **AI驱动的分析**: 预测性维护、良率预测、根因分析
- **数字孪生**: 虚拟设备镜像，What-If仿真分析
- **高可用架构**: Kubernetes原生，支持故障自动转移
- **企业级安全**: OAuth2/LDAP集成、电子签名、合规审计

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────┤
│  MES Layer │ Shared Services │ Device Control │ Data Layer│
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose (开发环境)
- Kubernetes 1.28+ (生产环境)

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/myeap.git
cd myeap

# 使用uv安装依赖
uv sync

# 运行测试
uv run pytest

# 启动开发服务器
uv run uvicorn myeap.api.main:app --reload
```

### 使用Docker Compose

```bash
docker-compose up -d
```

## 文档

- [用户文档](docs/user/)
- [开发者文档](docs/developer/)
- [API文档](docs/api/)
- [设计规范](docs/specs/)

## 项目结构

```
src/myeap/
├── core/          # 核心基础设施
├── mes/           # MES集成层
├── secs/          # SECS/GEM协议
├── device/        # 设备控制
├── recipe/        # 配方管理
├── alarm/         # 报警管理
├── tracking/      # 追踪服务
├── spc/           # SPC引擎
├── fdc/           # FDC引擎
├── ai/            # AI/ML模块
├── twin/          # 数字孪生
├── security/      # 安全服务
├── api/           # REST API
└── db/            # 数据库
```

## 开发

### 代码规范

```bash
# 代码格式化
uv run black .

# 导入排序
uv run isort .

# 代码检查
uv run ruff check .

# 类型检查
uv run mypy src/
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 带覆盖率
uv run pytest --cov=myeap --cov-report=html

# 特定模块
uv run pytest tests/unit/secs/
```

## 许可证

MIT License - see [LICENSE](LICENSE)
