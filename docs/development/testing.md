# Testing

本页记录第一版必须能在本地和 CI 中通过的校验命令。

## 环境变量

在仓库根目录设置包源码路径：

```powershell
$env:PYTHONPATH="$PWD\packages\agomtui-core\src;$PWD\packages\agomtui-compiler\src;$PWD\packages\agomtui-runtime\src"
```

Linux / GitHub Actions 使用冒号分隔：

```bash
export PYTHONPATH="$PWD/packages/agomtui-core/src:$PWD/packages/agomtui-compiler/src:$PWD/packages/agomtui-runtime/src"
```

## 单元测试

Core runtime contract tests：

```powershell
python -m unittest discover packages\agomtui-core\tests
```

Compiler tests：

```powershell
python -m unittest discover packages\agomtui-compiler\tests
```

Runtime asset and non-Django host example tests：

```powershell
python -m unittest discover packages\agomtui-runtime\tests
```

Django host tests：

```powershell
python demo\django_host\manage.py test django_host
```

## Metadata schema 校验

Minimal metadata：

```powershell
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
```

Rich component metadata：

```powershell
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\rich_components.tui_operation_graph.json
```

Generic operations metadata：

```powershell
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\generic_operations.tui_operation_graph.json
```

## Metadata 可用性检查

可用性检查会先执行 metadata schema / contract 校验，再检查屏幕、dashboard panel、action、field 和 view model 是否具备可操作的基本线索。`error` 会让命令返回非 0，`warning` 默认只报告不阻断；需要在本地收紧时可加 `--fail-on-warning`。

Minimal metadata：

```powershell
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\minimal.tui_operation_graph.json
```

Rich component metadata：

```powershell
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\rich_components.tui_operation_graph.json
```

Generic operations metadata：

```powershell
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\generic_operations.tui_operation_graph.json
```

## 验收标准

- core tests、compiler tests、runtime tests、Django host tests 全部通过。
- `minimal`、`rich_components` 和 `generic_operations` 示例 metadata 都通过 schema 校验。
- `minimal`、`rich_components` 和 `generic_operations` 示例 metadata 都通过可用性检查，且没有 `error`。
- 修改 governance、schema、collector 或 adapter 行为时，测试应覆盖对应 contract。
