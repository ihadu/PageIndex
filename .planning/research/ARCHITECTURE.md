# Architecture Research

**Domain:** 采购评分项知识库增强（类型分类 + 权重 + 政策性评分项）
**Researched:** 2026-04-17
**Confidence:** HIGH（基于现有代码深入分析）

## 现有架构分析

### 当前系统结构

```
┌─────────────────────────────────────────────────────────────┐
│                    VisionPageIndexClient                      │
│  (retrieve_with_expansion → ProcurementKnowledgeBase)        │
├─────────────────────────────────────────────────────────────┤
│                   ProcurementKnowledgeBase                    │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              PROCUREMENT_REQUIREMENTS_KNOWLEDGE        │   │
│  │  (Python Dict: 9种评分项扁平结构)                       │   │
│  │  - 人员配备、类似业绩、设备能力、企业资质...            │   │
│  │  - 每项含: category, title_keywords, material_types    │   │
│  └───────────────────────────────────────────────────────┘   │
│  方法: parse_intent, get_material_keywords, check_page_is_material │
├─────────────────────────────────────────────────────────────┤
│                     KBBuilder 工具链                          │
│  TenderParser → KeywordDiscovery → KBValidator → KBManager   │
│  → ExpertKBEnricher                                          │
├─────────────────────────────────────────────────────────────┤
│                      持久化层                                 │
│  JSON 文件存储 (workspace/*.json)                            │
│  无数据库依赖                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 现有数据结构

```python
# 当前: 平扁 Dict 结构
PROCUREMENT_REQUIREMENTS_KNOWLEDGE = {
    "人员配备": {
        "category": "人员类",
        "title_keywords": [...],
        "material_types": {
            "操作证": {"keywords": [...], "description": "..."},
            "培训证明": {"keywords": [...]},
        },
        "page_expansion_rule": {...}
    },
    "类似业绩": {...},
    # ... 9种评分项
}
```

### 现有方法签名

| 方法 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `parse_intent(query)` | 查询字符串 | Dict (requirement_type, keywords...) | VisionPageIndexClient 检索入口 |
| `get_material_keywords(req_type)` | 评分项类型 | List[str] | 扫描证明材料页 |
| `check_page_is_material(summary, req_type)` | 页面摘要 | Dict (is_material, type) | 判断页面是否为证明材料 |
| `get_all_requirement_types()` | 无 | List[str] | Agent 工具调用 |
| `get_category_requirements(category)` | 类别名 | List[str] | 按类别查询 |

---

## 新增功能架构集成

### 推荐架构: 类型分层 + 权重内嵌 + 政策项扩展

```
┌─────────────────────────────────────────────────────────────┐
│                    PROCUREMENT_TYPE_KNOWLEDGE                 │
│  (新增: 采购类型顶层分类)                                     │
│  ┌─────────────────────┐   ┌─────────────────────┐          │
│  │       货物类         │   │       服务类         │          │
│  │  price_weight: 30-50│   │  price_weight: 10-30│          │
│  │  key_reqs: 设备能力 │   │  key_reqs: 人员配备 │          │
│  │  requirements: {...}│   │  requirements: {...}│          │
│  └─────────────────────┘   └─────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│              PROCUREMENT_REQUIREMENTS_KNOWLEDGE               │
│  (保持现有结构 + 扩展政策性评分项)                             │
│  - 现有9种评分项: 人员配备、类似业绩...                        │
│  - 新增政策性评分项: 中小企业声明函、绿色产品认证              │
│  - 每项增加: procurement_types (适用采购类型)                 │
│  - 每项增加: weight_range (可选权重范围)                      │
├─────────────────────────────────────────────────────────────┤
│                   ProcurementKnowledgeBase (增强)             │
│  新增方法:                                                    │
│  - get_procurement_type_config(type)                         │
│  - get_requirements_for_type(procurement_type)               │
│  - parse_intent_with_type(query, procurement_type)           │
│  - get_weight_info(requirement_type, procurement_type)       │
│  - get_policy_requirements(procurement_type)                 │
├─────────────────────────────────────────────────────────────┤
│                     VisionPageIndexClient                     │
│  修改: retrieve_with_expansion 增加 procurement_type 参数    │
│  新增: retrieve_with_type_filter(doc_id, query, proc_type)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 详细数据结构设计

### 1. 采购类型分类层

```python
PROCUREMENT_TYPE_KNOWLEDGE = {
    "货物类": {
        "description": "货物采购项目（设备、物资、产品等）",
        "price_weight_range": {"min": 30, "max": 50},
        "key_requirements": ["设备能力", "企业资质", "报价响应"],
        "typical_materials": ["发票", "质量证明", "设备清单"],
        "evaluation_focus": "性价比、质量证明、设备配置",
        "policy_requirements": ["中小企业声明函", "绿色产品认证"],
    },
    "服务类": {
        "description": "服务采购项目（技术服务、咨询服务等）",
        "price_weight_range": {"min": 10, "max": 30},
        "key_requirements": ["人员配备", "类似业绩", "技术方案"],
        "typical_materials": ["合同", "业绩证明", "人员证书"],
        "evaluation_focus": "人员资质、业绩经验、方案质量",
        "policy_requirements": ["中小企业声明函"],
    },
}
```

### 2. 评分项增强结构

```python
PROCUREMENT_REQUIREMENTS_KNOWLEDGE = {
    # 现有评分项（增强字段）
    "人员配备": {
        "category": "人员类",
        "procurement_types": ["服务类"],  # 新增: 适用采购类型
        "weight_range": {"货物类": None, "服务类": {"min": 10, "max": 25}},  # 新增
        "title_keywords": [...],
        "material_types": {...},
        ...
    },
    "设备能力": {
        "category": "设备类",
        "procurement_types": ["货物类"],  # 新增
        "weight_range": {"货物类": {"min": 15, "max": 25}, "service类": None},  # 新增
        ...
    },

    # 新增: 政策性评分项
    "中小企业声明函": {
        "category": "政策类",
        "procurement_types": ["货物类", "服务类"],  # 两种类型都有
        "weight_range": {"货物类": {"min": 3, "max": 5}, "服务类": {"min": 3, "max": 5}},
        "description": "中小企业身份声明，享受政策优惠加分",
        "title_keywords": ["中小企业声明函", "中小企业声明", "小微企业声明"],
        "material_types": {
            "声明函": {
                "keywords": ["中小企业声明函", "小微企业声明", "中小企业认定"],
                "description": "企业类型声明文件",
                "is_policy_doc": True,  # 新增标记
            },
            "证明材料": {
                "keywords": ["营业执照", "企业规模说明", "从业人员数"],
                "description": "佐证企业类型的材料",
            },
        },
        "page_expansion_rule": {"direction": "forward", "max_pages": 3},
        "is_policy_requirement": True,  # 新增标记
        "policy_type": "中小企业扶持",  # 新增
    },
    "绿色产品认证": {
        "category": "政策类",
        "procurement_types": ["货物类"],  # 仅货物类适用
        "weight_range": {"货物类": {"min": 2, "max": 5}},
        "description": "绿色产品认证加分项",
        "title_keywords": ["绿色产品认证", "环保产品", "节能认证"],
        "material_types": {
            "认证证书": {
                "keywords": ["绿色产品认证证书", "环保认证", "节能认证证书"],
                "description": "绿色产品认证文件",
                "is_policy_doc": True,
            },
        },
        "page_expansion_rule": {"direction": "forward", "max_pages": 2},
        "is_policy_requirement": True,
        "policy_type": "绿色采购",
    },
}
```

---

## 组件职责边界

### 现有组件修改

| 组件 | 修改内容 | 保持兼容 |
|------|----------|----------|
| `ProcurementKnowledgeBase.__init__` | 加载 `PROCUREMENT_TYPE_KNOWLEDGE` | 向后兼容 |
| `parse_intent` | 增加 `procurement_type` 可选参数 | 默认参数保持兼容 |
| `get_all_requirement_types` | 增加 `procurement_type` 过滤参数 | 默认返回全部 |
| VisionPageIndexClient.retrieve_with_expansion | 增加 `procurement_type` 参数 | 默认 None |

### 新增组件

| 新组件 | 职责 | 位置 |
|--------|------|------|
| `ProcurementTypeClassifier` | 采购类型识别（从采购文件标题/内容） | procurement_kb_builder.py |
| `PolicyRequirementHandler` | 政策性评分项特殊处理逻辑 | procurement_knowledge.py |
| `WeightConfigLoader` | 权重配置加载（支持项目级覆盖） | procurement_kb_builder.py |

---

## 数据流变化

### 检索流程变化

```
[用户查询: "人员配备在哪几页"]
    ↓
VisionPageIndexClient.retrieve_with_expansion
    ↓
┌─ 新增: procurement_type 参数 (可选)
│   - None: 全量检索（默认，保持兼容）
│   - "货物类": 仅检索货物类相关评分项
│   - "服务类": 仅检索服务类相关评分项
↓
ProcurementKnowledgeBase.parse_intent(query, procurement_type=None)
    ↓
┌─ 新增步骤: 类型过滤
│   - 如果 procurement_type 指定
│   - 过滤: requirement.procurement_types 包含 procurement_type
↓
返回: requirement_type, title_keywords, material_types...
    ↓
后续流程不变: 标题页定位 → 证明材料页扫描 → 合并范围
```

### 知识库构建流程变化

```
[采购文件: "招标文件.pdf"]
    ↓
TenderParser.extract_from_tender
    ↓
┌─ 新增: 识别采购类型
│   - LLM 提取: "本项目为服务采购..."
│   - 分类为 "货物类" 或 "服务类"
│   - 存储: kb_dict["procurement_type"] = "服务类"
↓
┌─ 新增: 提取权重配置
│   - LLM 提取各评分项分值
│   - 存储: req["weight"] = 10
│   - 验证权重是否在 type 配置范围内
↓
┌─ 新增: 检查政策性评分项
│   - 识别是否包含中小企业声明函要求
│   - 识别是否包含绿色产品认证要求
│   - 自动添加到 kb_dict["requirements"]
↓
KBManager.save(kb_dict)
```

---

## 构建顺序建议

### Phase 1: 类型分类层 (优先级最高)

**原因:** 类型分类是后续权重和政策项的基础约束

**修改文件:**
1. `procurement_knowledge.py` - 添加 `PROCUREMENT_TYPE_KNOWLEDGE`
2. `procurement_knowledge.py` - `ProcurementKnowledgeBase` 新增类型相关方法
3. `procurement_kb_builder.py` - `TenderParser` 添加类型识别逻辑

**新增方法:**
```python
class ProcurementKnowledgeBase:
    def get_procurement_type_config(self, procurement_type: str) -> Dict
    def get_requirements_for_type(self, procurement_type: str) -> List[str]
    def parse_intent_with_type(self, query: str, procurement_type: str) -> Dict
```

### Phase 2: 评分项增强 (依赖 Phase 1)

**原因:** 需要类型层来确定 `procurement_types` 字段值

**修改文件:**
1. `procurement_knowledge.py` - 现有评分项添加 `procurement_types` 字段
2. `procurement_knowledge.py` - `parse_intent` 方法添加类型过滤逻辑

**向后兼容:**
```python
def parse_intent(self, query: str, procurement_type: str = None) -> Dict:
    # procurement_type=None 时行为与现有完全一致
```

### Phase 3: 权重配置 (可并行)

**原因:** 权重配置独立于检索逻辑，不影响核心功能

**修改文件:**
1. `procurement_knowledge.py` - 添加 `weight_range` 字段到评分项
2. `procurement_kb_builder.py` - `TenderParser` 提取权重
3. 新增 `WeightConfigLoader` 类

**用途:** 报告生成、合规性检查（不影响检索定位）

### Phase 4: 政策性评分项 (依赖 Phase 1, 2)

**原因:** 政策项需要类型层确定适用范围，需要评分项增强结构

**修改文件:**
1. `procurement_knowledge.py` - 添加政策性评分项定义
2. `procurement_knowledge.py` - 新增 `get_policy_requirements` 方法
3. `procurement_kb_builder.py` - `TenderParser` 添加政策项识别

### Phase 5: Vision 集成 (最后)

**原因:** 依赖所有底层结构完成

**修改文件:**
1. `vision_pageindex.py` - `retrieve_with_expansion` 添加 `procurement_type` 参数
2. `vision_pageindex.py` - Agent 工具函数添加类型相关工具

---

## API 向后兼容策略

### 兼容性矩阵

| API | 现有调用方式 | 新增调用方式 | 兼容性 |
|-----|-------------|-------------|--------|
| `ProcurementKnowledgeBase()` | `kb = ProcurementKnowledgeBase()` | 同上 | 完全兼容 |
| `parse_intent(query)` | `kb.parse_intent("人员配备")` | 同上 | 完全兼容（默认无类型过滤） |
| `parse_intent(query, type)` | 不存在 | `kb.parse_intent("人员配备", "服务类")` | 新增功能 |
| `get_all_requirement_types()` | `kb.get_all_requirement_types()` | 同上 | 完全兼容 |
| `get_requirements_for_type(type)` | 不存在 | `kb.get_requirements_for_type("货物类")` | 新增功能 |
| `retrieve_with_expansion(...)` | `client.retrieve_with_expansion(doc_id, query)` | 同上 | 完全兼容 |
| `retrieve_with_expansion(..., type)` | 不存在 | `client.retrieve_with_expansion(doc_id, query, procurement_type="货物类")` | 新增功能 |

### 兼容性实现模式

```python
# 所有新增参数使用默认值 None
def parse_intent(self, query: str, procurement_type: str = None) -> Dict:
    """
    解析用户查询的评分项意图

    Args:
        query: 用户查询
        procurement_type: 采购类型过滤（可选）
                         None = 不过滤（默认，保持兼容）
                         "货物类" = 仅返回货物类评分项
                         "服务类" = 仅返回服务类评分项
    """
    # 当 procurement_type=None 时，行为与现有版本完全一致
    ...
```

---

## 反模式警告

### 反模式 1: 类型分类与评分项解耦存储

**错误做法:**
```python
# 独立文件存储类型配置
type_config.json  # {"货物类": {...}, "服务类": {...}}
requirements.json # 现有评分项
```

**问题:** 查询时需要跨文件关联，增加复杂度

**正确做法:** 类型配置嵌入知识库结构，内存中统一 Dict

### 反模式 2: 权重影响检索逻辑

**错误做法:**
```python
# 权重高的评分项优先检索
if weight > 20:
    search_priority = "high"
```

**问题:** 检索目标是定位页码，权重不影响页码位置

**正确做法:** 权重仅用于报告、合规检查，不影响 `retrieve_with_expansion`

### 反模式 3: 政策性评分项单独处理流程

**错误做法:**
```python
# 政策项使用不同的检索逻辑
if is_policy_requirement:
    special_policy_search(...)
```

**问题:** 增加代码复杂度，政策项本质也是评分项

**正确做法:** 政策项纳入统一 `material_types` 结构，仅增加标记字段

---

## 测试策略

### 兼容性测试

```python
# 确保现有调用方式不受影响
def test_backward_compatibility():
    kb = ProcurementKnowledgeBase()

    # 现有方法签名不变
    result = kb.parse_intent("人员配备")
    assert result["requirement_type"] == "人员配备"

    # 现有方法返回结构不变
    keywords = kb.get_material_keywords("人员配备")
    assert "操作证" in keywords

    # 现有 Vision 检索不变
    client = VisionPageIndexClient()
    result = client.retrieve_with_expansion(doc_id, "人员配备")
    assert "page_ranges" in result
```

### 新功能测试

```python
def test_procurement_type_filter():
    kb = ProcurementKnowledgeBase()

    # 类型过滤
    goods_reqs = kb.get_requirements_for_type("货物类")
    assert "设备能力" in goods_reqs
    assert "人员配备" not in goods_reqs  # 服务类专用

    # 类型增强检索
    result = kb.parse_intent("设备能力", procurement_type="货物类")
    assert result["procurement_types"] == ["货物类"]

def test_policy_requirements():
    kb = ProcurementKnowledgeBase()

    # 政策项识别
    policy_reqs = kb.get_policy_requirements("货物类")
    assert "中小企业声明函" in policy_reqs
    assert "绿色产品认证" in policy_reqs

    # 政策项材料检测
    result = kb.check_page_is_material(
        "中小企业声明函页",
        "中小企业声明函"
    )
    assert result["is_material"] == True
    assert result["is_policy_doc"] == True  # 新增标记
```

---

## 文件变更清单

### 新增内容

| 文件 | 新增内容 | 行数估计 |
|------|----------|----------|
| `procurement_knowledge.py` | `PROCUREMENT_TYPE_KNOWLEDGE` Dict | ~30行 |
| `procurement_knowledge.py` | 政策性评分项定义（2项） | ~60行 |
| `procurement_knowledge.py` | 现有9项 `procurement_types` 字段 | 9行 |
| `procurement_knowledge.py` | 新增方法（5个） | ~100行 |
| `procurement_kb_builder.py` | 类型识别逻辑 | ~50行 |
| `procurement_kb_builder.py` | 政策项识别逻辑 | ~30行 |
| `vision_pageindex.py` | 类型参数支持 | ~20行 |

### 修改内容

| 文件 | 修改位置 | 修改类型 |
|------|----------|----------|
| `procurement_knowledge.py` | `parse_intent` | 添加可选参数 + 类型过滤 |
| `procurement_knowledge.py` | `ProcurementKnowledgeBase.__init__` | 加载类型配置 |
| `procurement_kb_builder.py` | `TenderParser._map_to_kb_structure` | 添加类型识别 |
| `vision_pageindex.py` | `retrieve_with_expansion` | 添加可选参数 |

---

## 来源

- 现有代码分析: `pageindex/procurement_knowledge.py` (v1.0)
- 现有代码分析: `pageindex/procurement_kb_builder.py` (v1.0)
- 现有代码分析: `pageindex/vision_pageindex.py` (v1.0)
- 项目需求: `.planning/PROJECT.md` v1.1 里程碑

---
*Architecture research for: PageIndex 采购评分项知识库增强*
*Researched: 2026-04-17*