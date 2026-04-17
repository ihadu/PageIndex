# State

## Current Position

Phase: Not started (milestone initialized, research complete)
Plan: —
Status: Ready for requirements definition
Last activity: 2026-04-17 — Research complete, POLICY-02 deferred to v1.x

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-17)

**Core value:** 让评审专家快速定位评分项页码
**Current focus:** 政府采购场景增强里程碑

## Accumulated Context

<!-- 从上一个里程碑继承的上下文 -->

### Key Learnings from v1.0

1. **轻量级设计有效**：Python Dict + JSON 无数据库依赖
2. **法规对齐关键**：评分项与财政部87号令对齐确保合规性
3. **排除词机制必要**：过滤偏离表等干扰页面提高精准度
4. **扩展检索价值**：标题页 + 证明材料页合并解决核心痛点

### Known Issues

1. **货物/服务权重未区分**：价格关键词权重应差异化
2. **政策性评分项缺失**：小微企业声明函、绿色产品认证未覆盖
3. **地区差异未体现**：各省采购规则差异未纳入
4. **有效性校验缺失**：无法检测证明材料是否在有效期内
5. **工程类缺失**：安全生产许可证、施工资质未覆盖

### Technical Debt

- 知识库静态存储，需政策自动更新机制
- 摘要截断到100字符可能丢失关键信息
- 无置信度反馈机制
- 无审批流程（政府采购合规要求）

## Workspace Info

Workspace: PageIndex-clean
Branch: feat/vision-procurement-kb
Main branch: main