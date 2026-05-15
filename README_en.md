# MyEAP - Enterprise Equipment Automation Program

> For Semiconductor Manufacturing

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/fzrai/myeap?style=social)](https://github.com/fzrai/myeap/stargazers)
[![Build Status](https://img.shields.io/github/actions/workflow/status/fzrai/myeap/ci.yml)](https://github.com/fzrai/myeap/actions)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Capabilities](#core-capabilities)
3. [Quick Start](#quick-start)
4. [Features](#features)
5. [Architecture](#architecture)
6. [Tech Stack](#tech-stack)
7. [Project Structure](#project-structure)
8. [Development](#development)
9. [Contributing](#contributing)
10. [License](#license)

---

## Introduction

**MyEAP** is an enterprise-grade Equipment Automation Program designed for semiconductor manufacturing factories, fully compliant with SEMI standards, supporting intelligent control and management of 2000+ equipment.

### Target Scenarios

- Single Fab (50-2000 equipment)
- Multi-Fab centralized management
- 8-inch/12-inch wafer Fab
- Mature/Advanced process nodes

---

## Core Capabilities

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

## Quick Start

### Requirements

- Python 3.11+
- Docker & Docker Compose
- Kubernetes 1.28+ (Production)

### Installation

```bash
# Clone repository
git clone https://github.com/fzrai/myeap.git
cd myeap

# Install dependencies
uv sync

# Run tests
uv run pytest

# Start development server
uv run uvicorn myeap.api.main:app --reload
```

### Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Kubernetes Deployment

```bash
# Deploy to K8s
kubectl apply -f configs/k8s/

# Check pod status
kubectl get pods -n myeap
```

---

## Features

### 1. SECS/GEM Protocol Layer

| Feature | Description |
|---------|-------------|
| SECS-II Codec | SECS-II message encoding/decoding |
| HSMS Connection | HSMS connection management with heartbeat |
| GEM State Machine | GEM state machine (SEMI E30) |
| Standard Messages | Standard message handling (S1-S15) |
| Auto Reconnection | Auto reconnection with exponential backoff |
| Message Tracing | Message tracing and logging |

### 2. MES Integration Layer

| Feature | Description |
|---------|-------------|
| MQTT Adapter | MQTT pub/sub messaging |
| REST Adapter | REST API communication |
| Kafka Adapter | Kafka event streaming |
| Work Order Reception | Work order reception and processing |
| Status Reporting | Equipment status reporting |
| Alarm Reporting | Alarm information reporting |
| Throughput Reporting | Throughput data reporting |

### 3. Device Control Layer

| Feature | Description |
|---------|-------------|
| Equipment Abstraction | Unified equipment abstraction |
| Chamber Control | Multi-chamber coordination |
| Process Control | Process flow control |
| Plugin System | Plugin-based equipment support |
| Cleaner Plugin | Cleaner equipment plugin |
| CVD Plugin | CVD equipment plugin |

### 4. Recipe Management

| Feature | Description |
|---------|-------------|
| Recipe CRUD | Recipe create/read/update/delete |
| Version Control | Semantic version control |
| Approval Workflow | Recipe approval workflow |
| Upload/Download | Upload/download recipes to equipment |
| Recipe Comparison | Recipe diff comparison |
| Parameterized Templates | Parameterized recipe templates |
| Recipe Validation | Configurable validation rules |

### 5. Alarm Management

| Feature | Description |
|---------|-------------|
| Alarm Detection | Alarm detection and recognition |
| Alarm Severity | Severity levels (CRITICAL/MAJOR/MINOR/WARNING) |
| Alarm Notification | Multi-channel notifications (Email/SMS/Webhook) |
| Alarm Escalation | Automatic escalation mechanism |
| Alarm Acknowledgment | Alarm acknowledgment handling |
| Alarm Suppression | Temporary alarm suppression |
| Statistics | Alarm statistics and analysis |

### 6. Data Collection

| Feature | Description |
|---------|-------------|
| Real-time Collection | Real-time data collection |
| Time-based Sampling | Time-based sampling strategy |
| Change-based Sampling | Value change sampling |
| Statistical Sampling | Aggregated sampling |
| Smart Sampling | Signal feature-based smart sampling |
| Limit Monitoring | UCL/LCL/USL/LSL limit monitoring |

### 7. SPC/FDC Engine

| Feature | Description |
|---------|-------------|
| Control Charts | Control charts (X-bar, R, S, X-MR, C, U, P, NP) |
| SPC Rules | SPC rules (Westgard rules) |
| Process Capability | Capability indices (Cp, Cpk, Pp, Ppk) |
| FDC Detection | Fault detection and classification |
| Feature Extraction | Feature extraction algorithms |
| Anomaly Detection | Multiple anomaly detection algorithms |

### 8. Tracking Service

| Feature | Description |
|---------|-------------|
| Carrier Registration | Carrier registration (FOUP, FOSB) |
| Carrier Tracking | Carrier position tracking |
| Wafer Tracking | Wafer processing tracking |
| Chamber Mapping | Chamber position mapping |
| Traceability Queries | Traceability queries |
| Impact Analysis | Impact scope analysis |
| Forward Traceability | Forward traceability |
| Backward Traceability | Backward traceability |

### 9. AI/ML Module

| Feature | Description |
|---------|-------------|
| Predictive Maintenance | Equipment failure prediction |
| Yield Prediction | Batch yield prediction |
| Root Cause Analysis | Anomaly root cause analysis |
| Time Series Forecasting | Time series prediction |
| Anomaly Detection | Intelligent anomaly detection |

### 10. Observability

| Feature | Description |
|---------|-------------|
| Prometheus Metrics | Prometheus monitoring metrics |
| OpenTelemetry Tracing | Distributed tracing |
| Structured Logging | Structured logging |
| Health Checks | Liveness/Readiness probes |
| Alert Aggregation | Alert aggregation display |

### 11. Security & Compliance

| Feature | Description |
|---------|-------------|
| Authentication | Identity authentication and authorization |
| RBAC | Role-based access control |
| Audit Trail | Operation audit logging |
| Electronic Signature | Electronic signature (21 CFR Part 11) |
| Data Encryption | Data transmission encryption |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                         Ingress Layer                            │     │
│  │                    (Nginx Ingress + SSL)                         │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                      MES Integration Layer                       │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐    │     │
│  │  │   MQTT    │ │   REST    │ │   Kafka   │ │    Config    │    │     │
│  │  │  Adapter   │ │  Gateway  │ │  Consumer │ │   Registry   │    │     │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                      Shared Services Layer                       │     │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │     │
│  │  │ Recipe  │ │  Alarm  │ │  Data   │ │  Audit   │ │  SPC/FDC │  │     │
│  │  │ Manager │ │ Handler │ │Collector│ │  Logger  │ │  Engine  │  │     │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘  │     │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │     │
│  │  │Tracking│ │ Digital │ │   AI    │ │Predictive│ │ Adaptive │  │     │
│  │  │Service │ │  Twin   │ │ Analysis│ │Maintenance│ │Control  │  │     │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘  │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                      Device Control Layer                         │     │
│  │                                                                       │     │
│  │  ┌─────────────────────────────────────────────────────────┐    │     │
│  │  │              Device Supervisor (One Pod per Equipment)      │    │     │
│  │  │  ┌───────────┐ ┌───────────┐ ┌────────────────┐   │    │     │
│  │  │  │ SECS/GEM  │ │ Equipment │ │    Process    │   │    │     │
│  │  │  │   Driver  │ │   State   │ │   Controller  │   │    │     │
│  │  │  │           │ │  Machine   │ │               │   │    │     │
│  │  │  └───────────┘ └───────────┘ └────────────────┘   │    │     │
│  │  └─────────────────────────────────────────────────────────┘    │     │
│  │                                                                       │     │
│  │  [Cleaner] [CVD] [PVD] [Etcher] [Lithography] [Diffusion] [CMP] │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                          Data Layer                             │     │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐    │     │
│  │  │   Redis    │ │ PostgreSQL │ │ TimescaleDB │ │  MinIO  │    │     │
│  │  │  (Cache)   │ │ (Primary)  │ │  (Timeseries)│ │ (Recipe)│    │     │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘    │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Async Framework | asyncio, FastAPI, uvicorn |
| Protocol | pycomm3 (SECS/GEM/HSMS) |
| Messaging | Apache Kafka, MQTT |
| Database | PostgreSQL, Redis, TimescaleDB |
| Object Storage | MinIO (S3-compatible) |
| Container | Docker, Kubernetes |
| Monitoring | Prometheus, Grafana, Jaeger |
| AI/ML | PyTorch, scikit-learn, statsmodels |
| Security | OAuth2, JWT, LDAP |

---

## Project Structure

```
myeap/
├── src/myeap/                    # Source code
│   ├── core/                     # Core infrastructure
│   ├── observability/            # Observability
│   ├── db/                      # Database layer
│   ├── secs/                     # SECS/GEM protocol
│   ├── mes/                      # MES integration
│   ├── device/                  # Device control
│   ├── recipe/                   # Recipe management
│   ├── alarm/                    # Alarm management
│   ├── tracking/                 # Tracking service
│   ├── data/                     # Data collection
│   ├── spc/                      # SPC engine
│   ├── fdc/                      # FDC engine
│   ├── ai/                       # AI/ML module
│   ├── twin/                     # Digital twin
│   ├── security/                 # Security
│   └── api/                      # REST API
├── tests/                        # Tests
├── configs/                      # Configuration
├── docs/                         # Documentation
├── alembic/                      # Database migrations
├── docker-compose.yml           # Docker Compose
├── pyproject.toml              # Project config
├── README.md                    # Main entry
├── README_zh.md                # Chinese docs
└── README_en.md               # English docs
```

---

## Development

### Code Standards

```bash
# Format code
uv run black .

# Sort imports
uv run isort .

# Lint code
uv run ruff check .

# Type check
uv run mypy src/
```

### Testing

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=myeap --cov-report=html --cov-report=term

# Specific module
uv run pytest tests/unit/secs/
```

### Commit Convention

```
feat:     New feature
fix:      Bug fix
docs:     Documentation
style:    Code style
refactor: Refactoring
test:     Tests
chore:    Build/Tools
```

---

## Contributing

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'feat: Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Create a Pull Request

---

## License

This project is open source under the [MIT License](LICENSE).

---

<p align="center">
  <strong>Made with ❤️ for Semiconductor Manufacturing</strong>
</p>
