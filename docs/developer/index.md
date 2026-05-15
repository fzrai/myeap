# 开发者文档

欢迎开发者贡献MyEAP项目。本节提供开发指南。

## 内容

- [架构设计](architecture.md) - 系统架构详解

## 开发环境设置

### 1. 安装依赖

```bash
# 安装uv
pip install uv

# 安装项目依赖
uv sync --dev
```

### 2. 运行测试

```bash
uv run pytest
```

### 3. 代码规范

```bash
# 格式化代码
uv run black .

# 检查代码
uv run ruff check .

# 类型检查
uv run mypy src/
```

## 提交代码

1. Fork仓库
2. 创建功能分支
3. 编写代码和测试
4. 提交Pull Request

详细规范请参考 [CONTRIBUTING.md](../../CONTRIBUTING.md)
