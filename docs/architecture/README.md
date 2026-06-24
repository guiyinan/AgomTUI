# Architecture Docs

这里维护 AgomTUI 的长期产品边界和架构说明。

- [product-split.md](product-split.md)：说明哪些能力应该成为通用产品，哪些仍属于宿主项目。
- [compiler-architecture.md](compiler-architecture.md)：说明 collector、AI synthesizer、validation、publisher 的边界。
- [upstream-extraction-memo.md](upstream-extraction-memo.md)：记录从已有宿主实现提取通用能力时的规则和注意事项。

架构文档的核心原则是：AgomTUI 应该生成宿主无关的 runtime metadata，业务执行、权限、审计存储和专属词汇留在 host adapter 或 override 层。
