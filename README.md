<p align="center">
  <a href="README.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_zh.md">🇨🇳 中文</a>
</p>

# MyEAP - Enterprise Equipment Automation Program

> Enterprise-grade Equipment Automation Program for Semiconductor Manufacturing

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/fzrai/myeap?style=social)](https://github.com/fzrai/myeap/stargazers)
[![Build Status](https://img.shields.io/github/actions/workflow/status/fzrai/myeap/ci.yml)](https://github.com/fzrai/myeap/actions)

---

## Quick Start

```bash
git clone https://github.com/fzrai/myeap.git
cd myeap
uv sync
uv run pytest
uv run uvicorn myeap.api.main:app --reload
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      MES Integration Layer                       │       │
│  │    ┌──────────┐   ┌──────────┐   ┌──────────┐                  │       │
│  │    │   MQTT   │   │   REST   │   │  Kafka   │                  │       │
│  │    │  Adapter │   │  Gateway │   │ Consumer │                  │       │
│  │    └──────────┘   └──────────┘   └──────────┘                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      Shared Services Layer                       │       │
│  │    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │       │
│  │    │ Recipe │ │ Alarm  │ │  Data  │ │ Track  │ │ SPC/FDC  │  │       │
│  │    │ Manager│ │ Handler│ │Collect │ │Service │ │  Engine  │  │       │
│  │    └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      Device Control Layer                        │       │
│  │    ┌───────────┐   ┌───────────┐   ┌──────────────────┐        │       │
│  │    │ SECS/GEM  │   │ Equipment │   │    Process       │        │       │
│  │    │  Driver   │   │   State   │   │   Controller     │        │       │
│  │    └───────────┘   └───────────┘   └──────────────────┘        │       │
│  │                                                                       │       │
│  │    [Cleaner] [CVD] [PVD] [Etcher] [Lithography] [CMP] ...          │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                          Data Layer                              │       │
│  │    ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐      │       │
│  │    │   Redis   │ │PostgreSQL │ │TimescaleDB│ │  MinIO  │      │       │
│  │    │  (Cache)  │ │ (Primary) │ │(Timeseries)│ │ (Recipe)│      │       │
│  │    └───────────┘ └───────────┘ └───────────┘ └─────────┘      │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### SECS/GEM Protocol
- SECS-II message encoding/decoding
- HSMS connection management with heartbeat
- GEM state machine (SEMI E30)
- Standard message handling (S1-S15)
- Auto reconnection with exponential backoff

### MES Integration
- MQTT adapter (pub/sub messaging)
- REST API gateway
- Kafka adapter (event streaming)
- Work order reception and status reporting
- Alarm and throughput reporting

### Equipment Control
- Unified equipment abstraction
- Multi-chamber coordination
- Process flow control
- Plugin-based equipment support
- Cleaner, CVD, PVD, Etcher plugins

### Recipe Management
- Version control (semantic versioning)
- Approval workflow
- Upload/download to equipment
- Recipe comparison
- Parameterized templates

### Alarm Management
- Multi-level severity (CRITICAL/MAJOR/MINOR/WARNING)
- Multi-channel notifications (Email/SMS/Webhook)
- Auto-escalation
- Alarm suppression
- Statistics and analytics

### Data Collection
- Real-time data collection
- Multiple sampling strategies (time, change, statistical, smart)
- Limit monitoring (UCL/LCL/USL/LSL)
- High-frequency process data

### SPC/FDC Engine
- Control charts (X-bar, R, S, X-MR, C, U, P, NP, EWMA, CUSUM)
- 8 Westgard SPC rules
- Process capability (Cp, Cpk, Pp, Ppk, sigma level)
- Fault detection and classification
- Feature extraction and anomaly detection

### Tracking & Traceability
- Carrier management (FOUP, FOSB)
- Wafer-level tracking
- Chamber mapping
- Forward/backward traceability
- Impact analysis

### Observability
- Prometheus metrics
- OpenTelemetry distributed tracing
- Structured logging
- Liveness/readiness health checks

### Security & Compliance
- OAuth2/LDAP authentication
- Role-based access control (RBAC)
- Audit trail
- Electronic signature (21 CFR Part 11)

## Development Status

| Module | Status | Tests |
|--------|--------|-------|
| SECS/GEM Protocol | ✅ Done | 47+ |
| MES Integration | ✅ Done | 81+ |
| Device Control | ✅ Done | 75+ |
| Recipe Management | ✅ Done | 105+ |
| Alarm Management | ✅ Done | 71+ |
| Data Collection | ✅ Done | 84+ |
| Tracking Service | ✅ Done | 62+ |
| SPC Engine | ✅ Done | 46+ |
| FDC Engine | ✅ Done | 89+ |
| Process Engine | 🔄 WIP | - |
| AI/ML Module | 🔄 WIP | - |
| Digital Twin | 🔄 WIP | - |

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Async Framework | asyncio, FastAPI, uvicorn |
| Protocol | pycomm3 (SECS/GEM/HSMS) |
| Messaging | Apache Kafka, MQTT |
| Database | PostgreSQL (Citus), Redis, TimescaleDB |
| Object Storage | MinIO (S3-compatible) |
| Container | Docker, Kubernetes |
| Monitoring | Prometheus, Grafana, Jaeger |
| AI/ML | PyTorch, scikit-learn |
| Security | OAuth2, JWT |

## Project Structure

```
myeap/
├── src/myeap/
│   ├── core/          # Core infrastructure
│   ├── observability/  # Observability
│   ├── db/            # Database
│   ├── secs/          # SECS/GEM protocol
│   ├── mes/           # MES integration
│   ├── device/        # Equipment control
│   ├── recipe/        # Recipe management
│   ├── alarm/         # Alarm management
│   ├── tracking/      # Tracking service
│   ├── data/          # Data collection
│   ├── spc/           # SPC engine
│   ├── fdc/           # FDC engine
│   ├── ai/            # AI/ML module
│   ├── twin/          # Digital twin
│   ├── security/      # Security
│   └── api/           # REST API
├── tests/             # Tests
├── configs/           # Config files
├── docs/              # Documentation
└── alembic/           # DB migrations
```

## Documentation

- [📖 English Full Documentation](README_en.md)
- [📖 完整中文文档](README_zh.md)
- [📋 API Reference](docs/api/)
- [🏗️ Architecture Design](docs/developer/architecture.md)

## Development

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Type check
uv run mypy src/

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=myeap --cov-report=html
```

## Contributing

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'feat: Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Create a Pull Request

## License

MIT License - see [LICENSE](LICENSE)

---

<p align="center">Made for Semiconductor Manufacturing</p>
