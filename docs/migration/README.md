# Migration Docs

这里维护 AgomTUI 从上游业务系统提取为独立产品的迁移路线。

- [migration-plan.md](migration-plan.md)：阶段计划和提取规则。

迁移过程中的硬规则：不要把 Agom 业务假设移进通用产品，除非它们被隔离在 adapter、vocabulary pack 或 reviewed metadata override 中。
