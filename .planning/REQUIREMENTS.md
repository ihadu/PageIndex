# Requirements: PageIndex v1.1

**Defined:** 2026-04-17
**Core Value:** 让评审专家快速定位评分项页码
**Milestone:** 货物/服务政府采购增强

## v1.1 Requirements

基于财政部87号令法定要求和研究结论，v1.1 实现采购类型分类、权重差异化、政策性评分项。

### 类型分类（TYPE）

- [ ] **TYPE-01**: 系统支持采购类型分类（货物类/服务类）
  - 顶层添加 `ProcurementType` 枚举（货物/服务）
  - `PROCUREMENT_TYPE_KNOWLEDGE` 配置每种类型的基础信息
  - API 向后兼容：新增参数默认值 `None`

- [ ] **TYPE-02**: 评分项权重按采购类型差异化配置
  - 每个评分项添加 `procurement_types` 适用类型字段
  - 每个评分项添加 `weight_range` 权重范围配置
  - 权重范围符合财政部87号令规定（货物价格30-50%，服务价格10-30%）

### 政策性评分项（POLICY）

- [ ] **POLICY-01**: 新增政策性评分项（中小企业声明函）
  - 添加 `政策性加分` 评分项类型
  - 定义中小企业声明函关键词：["中小企业声明函", "小微企业声明", "中小企业声明"]
  - 支持联合体声明函识别（4-6%扣除）
  - 纳入 `material_types` 统一结构，添加 `is_policy_doc` 标记字段

### API兼容性（COMPAT）

- [ ] **COMPAT-01**: 所有新增方法保持向后兼容
  - `parse_intent(query, procurement_type=None)` 默认行为不变
  - `get_material_keywords(requirement_type, procurement_type=None)` 默认行为不变
  - 现有 JSON 文件格式兼容（新增字段可选）

### 集成测试（INT）

- [ ] **INT-01**: VisionPageIndex 支持类型参数
  - `retrieve_with_expansion(doc_id, query, procurement_type=None)` 新增可选参数
  - 类型过滤不影响现有检索流程

## v1.x Requirements

延后到下一里程碑。

### 政策性评分项扩展

- **POLICY-02**: 新增政策性评分项（绿色产品认证）
  - 需品目清单数据库支持
  - 支持多种认证类型（中国环境标志、绿色建材认证等）
  - 认证有效期检测

### 地区差异化

- **REGION-01**: 构建地区知识库
  - 各省采购规则差异纳入
  - 省级权重范围配置

### 合规性检测

- **VALID-01**: 证明材料有效性检测
  - 证书有效期检测
  - 公章检测

## Out of Scope

明确排除，防止范围蔓延。

| Feature | Reason |
|---------|--------|
| 工程类采购 | 不属于政府采购范围（适用招标投标法） |
| 评分结果自动计算 | 仅定位评分项页码，不计算评分 |
| 证明材料合规性判定 | 需人工复核有效性 |
| 询价/竞争性谈判评审 | 仅支持综合评分法 |
| 国际采购 | 仅支持中文政府采购文件 |
| 企业自主采购 | 非政府采购规则 |

## Traceability

需求与阶段映射，路线图创建时更新。

| Requirement | Phase | Status |
|-------------|-------|--------|
| TYPE-01 | Phase 1 | Pending |
| TYPE-02 | Phase 2 | Pending |
| POLICY-01 | Phase 3 | Pending |
| COMPAT-01 | Phase 1 | Pending |
| INT-01 | Phase 4 | Pending |

**Coverage:**
- v1.1 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-17*
*Last updated: 2026-04-17 after research synthesis*