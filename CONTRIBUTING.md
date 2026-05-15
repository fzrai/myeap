# 贡献指南

感谢您对MyEAP项目的关注！欢迎提交Pull Request或报告Issue。

## 开发环境设置

1. 克隆仓库
2. 安装uv: `pip install uv`
3. 安装依赖: `uv sync`
4. 设置pre-commit hooks: `uv run pre-commit install`

## 代码规范

- 遵循PEP 8
- 使用Black格式化
- 使用isort排序导入
- 添加类型注解
- 编写单元测试

## Pull Request流程

1. Fork仓库
2. 创建功能分支
3. 提交更改
4. 推送分支
5. 创建Pull Request

## 提交规范

使用Conventional Commits:

- `feat:` 新功能
- `fix:` 修复bug
- `docs:` 文档更新
- `style:` 代码格式
- `refactor:` 重构
- `test:` 测试
- `chore:` 构建/工具
