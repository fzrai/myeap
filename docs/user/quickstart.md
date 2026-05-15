# 快速开始

本指南帮助您在5分钟内启动MyEAP系统。

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 4GB可用内存

## 步骤1: 克隆项目

```bash
git clone https://github.com/your-org/myeap.git
cd myeap
```

## 步骤2: 配置环境

复制环境变量文件：

```bash
cp .env.example .env
```

编辑`.env`文件，配置必要的参数。

## 步骤3: 启动服务

```bash
docker-compose up -d
```

等待所有服务启动完成。

## 步骤4: 验证

访问 http://localhost:8000/docs 查看API文档。

## 下一步

- 阅读[配置指南](configuration.md)了解详细配置
- 查看[开发者文档](../developer/)了解系统架构
