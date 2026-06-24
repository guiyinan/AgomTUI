# Development Guide

这个目录维护 AgomTUI 的开发约定和质量入口。

## 本地开发前提

- Python `>=3.11`。
- 当前仓库没有统一 workspace 安装脚本；本地运行包级测试时需要设置 `PYTHONPATH`。
- Django host demo 需要本地 Python 环境中安装 Django。

## 常用入口

- 开发标准：[development-standards.md](development-standards.md)
- 测试命令：[testing.md](testing.md)
- CI 护栏：[ci-guardrails.md](ci-guardrails.md)

## Host 示例

- Django host demo：`demo/django_host/`
- 非 Django 标准库 host：`examples/hosts/stdlib_host.py`

## 第一版质量策略

第一版先使用最小可落地护栏：现有 unittest、Django host tests、metadata schema 校验。暂不引入 Ruff、Black、mypy、coverage 或 pre-commit，避免在产品边界尚在快速收敛时增加额外维护面。
