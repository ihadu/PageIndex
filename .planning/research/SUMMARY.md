# Project Research Summary

**Project:** PageIndex 采购评分项知识库系统 v1.1
**Milestone:** 货物/服务政府采购增强（类型分类 + 权重 + 政策性评分项）
**Domain:** 中国政府采购 - 评分项检索定位系统
**Researched:** 2026-04-17
**Confidence:** HIGH

## Executive Summary

PageIndex v1.1 是对中国政府采购评分项知识库系统的重要增强，核心目标是实现**采购类型分类**和**政策性评分项识别**。这是基于财政部87号令法定要求的功能扩展：货物类和服务类采购评分权重范围不同（货物价格权重30-50%，服务10-30%），系统必须区分类型才能提供准确的检索服务。

推荐方案采用**轻量级架构扩展**：在现有 Python Dict + JSON 结构基础上，添加顶层类型分类层和内嵌权重配置，保持无数据库依赖的设计原则。新增政策性评分项（中小企业声明函、绿色产品认证）作为特殊类别纳入知识库，使用统一结构而非独立处理流程。

关键风险集中在**API向后兼容性**和**数据迁移完整性**。解决方案是所有新增参数使用默认值（procurement_type=None），确保现有调用方无需修改；数据迁移时采用渐进式策略，先复制到"通用"层再分化到"货物"和"服务"层，并通过验证机制检查完整性。

## Key Findings

### Recommended Stack

沿用现有轻量级技术栈，仅新增 Python 内置模块实现类型安全。无需引入数据库或配置管理框架，保持原型阶段的简洁设计。

**Core technologies:**
- **Python Dict + JSON**: 知识库存储 — 原型阶段轻量级设计，已在 v1.0 验证
- **enum.Enum**: 采购类型枚举 (`货物/服务`) — 类型安全，防止字符串硬编码
- **dataclasses**: 权重配置类 — 结构化权重范围，支持类型提示和验证
- **LiteLLM 1.83.0**: 多模型调用 — 支持 OpenAI、阿里云 DashScope
- **PyMuPDF 1.26.4**: PDF转图片 — 扫描件处理核心依赖

**不添加的技术:**
- 数据库（SQLite/PostgreSQL） — 原型阶段增加部署复杂度，用 JSON 持久化替代
- ORM框架 — 过度工程化，知识库数据量小
- 类型检查库（pydantic） — Python 内置 dataclasses 已足够

### Expected Features

基于财政部87号令和财库46号的法定要求，v1.1 必须实现三大功能。

**Must have (table stakes):**
- **采购类型分类 (TYPE-01)** — 法定要求，货物类和服务类评分权重不同，评审时必须区分
- **权重差异化配置 (TYPE-02)** — 法定要求，货物价格权重30-50%，服务10-30%
- **中小企业声明函识别 (POLICY-01)** — 财库46号强制要求，所有政府采购项目必备政策性评分项

**Should have (competitive):**
- **绿色产品认证检测 (POLICY-02)** — 政府采购绿色产品优先采购政策加分，增值检索能力（建议延后到 v1.x）

**Defer (v2+):**
- **智能权重推荐** — 基于历史项目数据建模，便利性提升
- **政策性评分项自动更新** — 需政策监测机制，长期规划
- **地区知识库差异化** — 各省采购规则差异，需地区级知识库

**Anti-features (明确拒绝):**
- 自动评分计算 — 评分需人工审核证明材料有效性，系统仅定位页码
- 证明材料有效性校验 — OCR+日期解析复杂度高，合规风险大
- 工程类采购扩展 — 适用招标投标法而非政府采购法，规则差异大

### Architecture Approach

采用**类型分层 + 权重内嵌 + 政策项扩展**架构。顶层新增 `PROCUREMENT_TYPE_KNOWLEDGE` 定义货物/服务类型配置，现有评分项结构保持不变，仅扩展 `procurement_types` 和 `weight_range` 字段。政策性评分项纳入统一的 `PROCUREMENT_REQUIREMENTS_KNOWLEDGE` 结构，通过 `is_policy_requirement` 标记区分，不使用独立处理流程。

**Major components:**
1. **ProcurementTypeClassifier** — 采购类型识别（从采购文件标题/内容），位于 `procurement_kb_builder.py`
2. **PolicyRequirementHandler** — 政策性评分项特殊处理逻辑（联合体投标、多重认证），位于 `procurement_knowledge.py`
3. **WeightConfigLoader** — 权重配置加载（支持项目级覆盖），位于 `procurement_kb_builder.py`

**Data structure changes:**
```python
# 新增顶层类型配置
PROCUREMENT_TYPE_KNOWLEDGE = {
    "货物类": {"price_weight_range": {"min": 30, "max": 50}, ...},
    "服务类": {"price_weight_range": {"min": 10, "max": 30}, ...}
}

# 现有评分项扩展字段
"人员配备": {
    "procurement_types": ["服务类"],  # 新增
    "weight_range": {"服务类": {"min": 10, "max": 25}},  # 新增
    ...
}

# 新增政策性评分项
"中小企业声明函": {
    "category": "政策类",
    "is_policy_requirement": True,
    ...
}
```

### Critical Pitfalls

基于现有代码分析和集成测试风险，识别以下关键陷阱。

1. **API向后兼容性破坏** — 现有 VisionPageIndex、KBValidator 等调用方因缺少新参数而失败
   - 预防：所有新增参数使用默认值 `procurement_type=None`，默认行为与现有完全一致
   - 验证：运行 `tests/test_procurement_kb.py` 确认无失败

2. **关键词索引重建遗漏** — 类型化索引未按货物/服务分别构建，导致权重差异无法应用
   - 预防：`_build_keyword_index()` 构建类型化结构 `{货物: {}, 服务: {}, 通用: {}}`
   - 验证：检查 `keyword_index["货物"]` 和 `keyword_index["服务"]` 非空

3. **权重计算精度与边界问题** — 权重总和溢出或边界值导致其他评分项负数
   - 那预防：权重验证机制 `validate_weights()` 检查总和100%、范围合规
   - 验证：权重总和测试，边界值配置测试

4. **政策性评分项边缘情况** — 联合体投标、多重认证等特殊情况漏检
   - 预防：结构化配置区分"小微企业声明函"和"联合体声明函"，验证规则检查格式
   - 验证：测试联合体声明函和多重认证识别

5. **数据结构迁移不完整** — 现有9种评分项迁移时遗漏或字段不完整
   - 预防：渐进式迁移（通用→货物/服务→删除通用类型特定项），迁移验证机制
   - 验证：新旧知识库评分项数量一致，字段完整

## Implications for Roadmap

基于研究依赖关系和架构设计，建议以下阶段顺序：

### Phase 1: 类型分类层 (TYPE-01)

**Rationale:** 类型分类是后续权重和政策项的基础约束，必须首先建立顶层架构。
**Delivers:** `PROCUREMENT_TYPE_KNOWLEDGE` 定义、`ProcurementTypeClassifier` 实现、类型枚举
**Addresses:** TYPE-01 采购类型分类功能
**Avoids:** API向后兼容性破坏（参数默认值）、关键词索引遗漏（类型化索引）

**修改文件:**
- `procurement_knowledge.py` — 添加类型配置 Dict、类型枚举
- `procurement_knowledge.py` — 新增方法 `get_procurement_type_config()`, `get_requirements_for_type()`
- `procurement_kb_builder.py` — `TenderParser` 添加类型识别逻辑

**Research flag:** 标准模式，无需额外研究（财政部法规依据明确）

### Phase 2: 评分项增强 (TYPE-02 权重差异化)

**Rationale:** 需要类型层确定 `procurement_types` 和 `weight_range` 字段值，依赖 Phase 1。
**Delivers:** 现有评分项添加类型适用字段、权重配置内嵌、权重验证机制
**Uses:** `enum.Enum`, `dataclasses`, 类型配置层
**Implements:** TYPE-02 权重差异化配置

**修改文件:**
- `procurement_knowledge.py` — 现有9项添加 `procurement_types`, `weight_range` 字段
- `procurement_knowledge.py` — `parse_intent()` 添加类型过滤逻辑
- `procurement_kb_builder.py` — 新增 `WeightConfigLoader` 类

**Avoids:** 权重计算精度问题（权重验证机制）、边界值异常（范围约束）

**Research flag:** 标准模式，无需额外研究（87号令权重范围明确）

### Phase 3: 政策性评分项 (POLICY-01 中小企业声明函)

**Rationale:** 政策项需要类型层确定适用范围（中小企业声明函适用货物和服务），依赖 Phase 1。
**Delivers:** 中小企业声明函定义、政策项检索逻辑、联合体特殊情况处理
**Addresses:** POLICY-01 中小企业声明函识别
**Avoids:** 政策性评分项边缘情况（结构化配置、验证规则）

**修改文件:**
- `procurement_knowledge.py` — 添加政策性评分项定义
- `procurement_knowledge.py` — 新增 `get_policy_requirements()`, `check_policy_compliance()` 方法
- `procurement_kb_builder.py` — `TenderParser` 添加政策项识别

**Research flag:** 可能需要研究 — 联合体投标声明函格式需确认财库46号具体规定

### Phase 4: 绿色产品认证 (POLICY-02，可选)

**Rationale:** 仅适用货物类，需关联品目清单数据，实现复杂度较高。
**Delivers:** 绿色产品认证检测、品目清单关联（可选）
**Addresses:** POLICY-02 绿色产品认证检测

**决策点:** **是否纳入 v1.1？**
- FEATURES 建议"Add After Validation"（延后实现）
- ARCHITECTURE 已设计完整结构
- 需要：品目清单数据关联，实现复杂度 MEDIUM

**建议:** 延后到 v1.x，v1.1 仅预留结构，不实现完整功能

**Research flag:** 需要研究 — 品目清单数据获取方式、绿色产品认证目录更新机制

### Phase 5: Vision 集成

**Rationale:** 依赖所有底层结构完成，是最终集成层。
**Delivers:** VisionPageIndexClient 支持 procurement_type 参数、Agent 工具函数扩展
**Uses:** 所有新增方法、类型配置、权重配置

**修改文件:**
- `vision_pageindex.py` — `retrieve_with_expansion()` 添加 `procurement_type` 参数
- `vision_pageindex.py` — Agent 工具函数添加类型相关工具

**Avoids:** API兼容性破坏（默认参数）、集成测试失败

**Research flag:** 标准模式，基于现有 Agent 集成经验

### Phase Ordering Rationale

- **Phase 1→2→3 顺序:** 类型分类是架构基础，权重和政策项都依赖类型层确定适用范围
- **Phase 1+3 可并行:** 中小企业声明函识别仅依赖类型层，与权重配置无强依赖
- **Phase 4 延后:** 绿色产品认证需品目清单数据，建议 v1.x 实现
- **Phase 5 最后:** Vision 集成是最终交付层，需底层结构全部稳定

### Research Flags

**需要研究阶段:**
- **Phase 3:** 联合体投标声明函具体格式（财库46号规定细节）
- **Phase 4:** 品目清单数据获取方式、绿色产品认证目录更新机制

**标准模式阶段（无需研究）:**
- **Phase 1:** 财政部87号令法规依据明确，类型分类规则简单
- **Phase 2:** 权重范围已法定规定，配置结构简单
- **Phase 5:** 基于 Agent 集成经验，模式已验证

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | 法规依据明确（87号令、财库46号），架构设计简洁，无需新增外部依赖 |
| Features | HIGH | Table Stakes 基于 statutory requirements，优先级清晰 |
| Architecture | HIGH | 基于现有代码深入分析，向后兼容策略明确 |
| Pitfalls | HIGH | 基于现有代码分析和测试用例调用点分析，预防措施具体 |

**Overall confidence:** HIGH

### Gaps to Address

研究过程中识别的待确认问题：

- **联合体投标声明函格式:** 财库46号规定联合体中小企业声明函的具体格式需确认，影响 Phase 3 实现
  - 处理方式: Phase 3 实现时查阅财库46号原文，或咨询政府采购专家

- **品目清单数据获取:** 绿色产品认证需关联品目清单，系统无此数据源
  - 处理方式: Phase 4 延后，先调研财政部品目清单公开数据获取方式

- **各省权重差异:** 87号令规定范围，各省可能有具体规定，当前仅实现范围配置
  - 处理方式: v1.1 实现范围配置，v2+ 考虑地区知识库差异化

### Open Questions (需用户确认)

1. **绿色产品认证纳入 v1.1？** — FEATURES 建议延后，ARCHITECTURE 已设计。建议：延后到 v1.x
2. **是否支持项目级权重覆盖？** — 各项目可能有不同权重配置，需确认是否支持
3. **政策性评分项自动识别？** — TenderParser 是否自动识别政策性评分项，还是手动配置

## Sources

### Primary (HIGH confidence)
- **财政部令第87号** — 《政府采购货物和服务招标投标管理办法》第55条，权重范围法定依据
- **财库〔2020〕46号** — 《政府采购促进中小企业发展管理办法》，中小企业声明函法定依据
- **现有代码分析** — `pageindex/procurement_knowledge.py`, `pageindex/vision_pageindex.py` (v1.0)

### Secondary (MEDIUM confidence)
- **docs/PROCUREMENT_KB_EVALUATION.md** — 识别的系统性问题，知识库扩展需求来源
- **tests/test_procurement_kb.py** — API调用模式分析，51个调用点兼容性验证

### Tertiary (LOW confidence)
- **市场监管总局绿色产品认证规定** — 加分范围2-5分，2026年起成为必要评分项（需验证具体文件）
- **节能产品政府采购清单** — 品目清单数据源（需调研获取方式）

---

**Research completed:** 2026-04-17
**Ready for roadmap:** yes
**Files synthesized:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md