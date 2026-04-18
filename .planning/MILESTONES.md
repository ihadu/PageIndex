# Milestones

## v1.0 — 采购评分项知识库基础版本

**Status:** ✓ Complete
**Date:** 2026-04-16

### Shipped

- 基础树结构索引（page_index.py）
- 视觉检索 VisionPageIndex（vision_pageindex.py）
- 多轮扩展检索（标题页 + 证明材料页合并）
- 采购评分项知识库（9种评分项映射）
- 关键词排除机制
- OpenAI Agents SDK 集成
- LiteLLM 兼容（阿里云 DashScope）
- 工作区持久化
- 知识库构建工具集

### Validation

- 综合评分：5.8/10（见评估文档）
- 适用于货物/服务类采购（综合评分法）
- 核心价值：评审专家快速定位评分项页码 ✓

---

## v1.1 — 政府采购场景增强

**Status:** ✓ Complete (Archived)
**Date:** 2026-04-17
**Archive:** `.planning/milestones/v1.1-ROADMAP.md`, `.planning/milestones/v1.1-REQUIREMENTS.md`

### Shipped

基于评估文档 PROCUREMENT_KB_EVALUATION.md 的改进计划：

- **TYPE-01**: 采购类型分类（ProcurementType 枚举）
- **TYPE-02**: 权重差异化配置（weight_range 字段）
- **POLICY-01**: 中小企业声明函识别
- **COMPAT-01**: API向后兼容
- **INT-01**: VisionPageIndex 类型参数

### Stats

- 新增代码: 2,045 lines
- 新增测试: 62 个（全部通过）
- Git range: 9febcb0 → 624296b

---

## v1.2 — 规划中

**Status:** 📋 Planned

### Potential Features

- **POLICY-02**: 绿色产品认证（需品目清单数据）
- **REGION-01**: 地区知识库差异化
- **VALID-01**: 证明材料有效性检测