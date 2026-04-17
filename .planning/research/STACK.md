# Stack Research

**Domain:** 政府采购评分项知识库 - 类型分类与政策性评分项
**Researched:** 2026-04-17
**Confidence:** HIGH (法规依据明确，架构设计简洁)

## 推荐技术栈

### 核心技术（沿用现有）

| 技术 | 版本 | 用途 | 推荐理由 |
|-----|-----|-----|---------|
| Python Dict + JSON | - | 知识库存储 | 轻量级设计，原型阶段无需数据库依赖，已在v1.0验证 |
| LiteLLM | 1.83.0 | 多模型调用 | 支持OpenAI、阿里云DashScope等，统一API格式 |
| PyMuPDF | 1.26.4 | PDF转图片 | 扫描件PDF处理核心，支持图片提取 |
| OpenAI Agents SDK | - | Agent集成 | 多工具协作检索，Chat Completions API兼容 |

### 新增内置模块

| 技术 | 版本 | 用途 | 推荐理由 |
|-----|-----|-----|---------|
| `enum.Enum` | Python内置 | 采购类型枚举 | 类型安全，防止"货物/服务"字符串硬编码 |
| `dataclasses` | Python内置 | 权重配置类 | 结构化权重范围，支持类型提示和验证 |

**核心设计原则：** 无需新增外部依赖，保持轻量级设计。

## 数据结构变更

### 采购类型分类层

```python
from enum import Enum

class ProcurementType(Enum):
    """采购类型枚举 - 货物类/服务类"""
    GOODS = "货物"      # 货物类采购
    SERVICES = "服务"   # 服务类采购

    @classmethod
    def from_string(cls, value: str) -> 'ProcurementType':
        """从字符串识别类型"""
        if "货物" in value or "设备" in value or "物资" in value:
            return cls.GOODS
        if "服务" in value or "运维" in value or "咨询" in value:
            return cls.SERVICES
        raise ValueError(f"未知采购类型: {value}")
```

### 权重配置结构

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class WeightConfig:
    """评分项权重配置"""
    requirement_type: str           # 评分项名称
    goods_weight_range: tuple       # 货物类权重范围 (min, max)
    services_weight_range: tuple    # 服务类权重范围 (min, max)
    typical_weight: Optional[float] = None  # 典型权重值

# 示例配置（基于财政部87号令）
WEIGHT_CONFIGS = {
    "价格评分": WeightConfig(
        requirement_type="报价响应",
        goods_weight_range=(30, 50),   # 货物：30-50%
        services_weight_range=(10, 30), # 服务：10-30%
        typical_weight=35
    ),
    "人员配备": WeightConfig(
        requirement_type="人员配备",
        goods_weight_range=(5, 15),
        services_weight_range=(10, 25),  # 服务类人员权重更高
    ),
    # ...其他评分项权重配置
}
```

### 知识库结构扩展

```python
# 原结构（v1.0）
PROCUREMENT_REQUIREMENTS_KNOWLEDGE = {
    "人员配备": {
        "category": "人员类",
        "title_keywords": [...],
        "material_types": {...},
        "page_expansion_rule": {...},
    }
}

# 新结构（v1.1）- 添加类型分类和权重层
PROCUREMENT_KNOWLEDGE_V2 = {
    "metadata": {
        "version": "v1.1",
        "procurement_types": ["货物", "服务"],
        "weight_source": "财政部87号令第55条",
    },
    "type_configs": {
        "货物": {
            "price_weight_min": 30,  # 法定最低30%
            "price_weight_max": 50,
            "key_scoring_items": ["设备能力", "质量证明", "发票"],
        },
        "服务": {
            "price_weight_min": 10,  # 法定最低10%
            "price_weight_max": 30,
            "key_scoring_items": ["人员配备", "类似业绩", "技术方案"],
        },
    },
    "policy_scoring_items": {
        "中小企业声明函": {
            "category": "政策类",
            "benefit_type": "price_deduction",  # 价格扣除优惠
            "deduction_range": (6, 10),         # 6%-10%
            "title_keywords": ["中小企业声明函", "小微企业声明", "中小企业证明"],
            "material_types": {
                "声明函": {"keywords": ["中小企业声明函", "小微企业声明函"]}
            },
            "format_reference": "财库〔2020〕46号",
        },
        "绿色产品认证": {
            "category": "政策类",
            "benefit_type": "scoring_bonus",    # 评分加分
            "bonus_range": (2, 5),              # 2-5分
            "title_keywords": ["绿色产品认证", "环保产品认证", "绿色认证证书"],
            "material_types": {
                "认证证书": {"keywords": ["绿色产品认证证书", "环保认证"]}
            },
            "mandatory_2026": True,             # 2026年起成为必要评分项
        },
    },
    "requirements": PROCUREMENT_REQUIREMENTS_KNOWLEDGE,  # 沿用v1.0结构
}
```

## 集成点设计

### 1. `procurement_knowledge.py` 集成

```python
class ProcurementKnowledgeBase:
    """采购评分项知识库 - v1.1 增强版"""

    def __init__(self, procurement_type: ProcurementType = None):
        """
        Args:
            procurement_type: 采购类型（货物/服务），可选
        """
        self.procurement_type = procurement_type
        self.knowledge = PROCUREMENT_KNOWLEDGE_V2
        self._build_keyword_index()

    def get_weight_config(self, requirement_type: str) -> WeightConfig:
        """获取评分项权重配置（按采购类型）"""
        return WEIGHT_CONFIGS.get(requirement_type)

    def get_policy_items(self) -> List[str]:
        """获取政策性评分项列表"""
        return list(self.knowledge.get("policy_scoring_items", {}).keys())

    def check_policy_compliance(
        self,
        page_summary: str,
        policy_type: str
    ) -> Dict:
        """检查政策性评分项材料"""
        policy_config = self.knowledge["policy_scoring_items"].get(policy_type)
        if not policy_config:
            return {"compliant": False, "reason": "未知政策类型"}

        # 检查关键词匹配
        matched = []
        for mat_type, mat_config in policy_config.get("material_types", {}).items():
            for kw in mat_config.get("keywords", []):
                if kw in page_summary:
                    matched.append(kw)

        return {
            "compliant": len(matched) > 0,
            "matched_keywords": matched,
            "benefit_type": policy_config.get("benefit_type"),
            "benefit_range": policy_config.get("deduction_range") or policy_config.get("bonus_range"),
        }
```

### 2. `vision_pageindex.py` 集成

```python
def retrieve_with_expansion(
    self,
    doc_id: str,
    query: str,
    procurement_type: ProcurementType = None,  # 新增参数
    include_policy_items: bool = True,         # 新增参数
    max_images: int = 10,
    knowledge_base: ProcurementKnowledgeBase = None
) -> Dict[str, Any]:
    """
    多轮扩展检索 - v1.1 增强版

    Args:
        procurement_type: 采购类型（货物/服务），影响权重提示
        include_policy_items: 是否包含政策性评分项检索
    """
    kb = knowledge_base or ProcurementKnowledgeBase(procurement_type)

    # 原有检索逻辑...
    result = self._retrieve_requirement(doc_id, query, kb)

    # 新增：政策性评分项检索
    if include_policy_items:
        policy_items = kb.get_policy_items()
        policy_results = {}
        for policy_type in policy_items:
            policy_check = kb.check_policy_compliance(
                page_summaries=self.page_summaries.get(doc_id, {}),
                policy_type=policy_type
            )
            if policy_check["compliant"]:
                policy_results[policy_type] = policy_check
        result["policy_items"] = policy_results

    return result
```

### 3. Agent 工具函数集成

```python
@function_tool
def get_procurement_type_config(procurement_type: str) -> str:
    """获取采购类型权重配置信息。参数: procurement_type - '货物' 或 '服务'"""
    try:
        ptype = ProcurementType.from_string(procurement_type)
        config = PROCUREMENT_KNOWLEDGE_V2["type_configs"][ptype.value]
        return json.dumps({
            'type': ptype.value,
            'price_weight_range': f"{config['price_weight_min']}-{config['price_weight_max']}%",
            'key_scoring_items': config['key_scoring_items'],
        }, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({'error': str(e)})

@function_tool
def check_policy_scoring_items(doc_id: str) -> str:
    """检查文档中的政策性评分项（中小企业声明函、绿色产品认证）"""
    # ...检查逻辑
```

## 不添加的技术

| 避免 | 原因 | 替代方案 |
|-----|-----|---------|
| 数据库（SQLite/PostgreSQL） | 原型阶段，增加部署复杂度 | Python Dict + JSON持久化 |
| ORM框架 | 过度工程化，知识库数据量小 | 直接dict操作 |
| 配置管理库（hydra/confit） | 权重配置简单，无需复杂框架 | dataclasses + YAML |
| 类型检查库（pydantic） | 已有typing模块，dataclasses足够 | Python内置dataclasses |
| 机器学习分类器 | 采购类型识别规则简单，关键词匹配足够 | 字符串匹配 + Enum |

## 版本兼容性

| 包 | 版本 | 兼容性 | 备注 |
|---|-----|-------|-----|
| litellm | 1.83.0 | 稳定 | 已验证OpenAI/DashScope调用 |
| pymupdf | 1.26.4 | 稳定 | PDF转图片核心依赖 |
| Python | 3.10+ | 需要 | dataclasses需要3.10+特性 |

## 安装说明

```bash
# 无需新增安装 - 所有依赖均为Python内置模块
# 现有依赖保持不变
pip install litellm==1.83.0
pip install pymupdf==1.26.4
pip install PyPDF2==3.0.1
pip install python-dotenv==1.1.0
pip install pyyaml==6.0.2
```

## 法规依据

### 财政部87号令（政府采购货物和服务招标投标管理办法）

**第55条 - 综合评分法权重规定：**
- 货物项目价格分值权重不得低于30%
- 服务项目价格分值权重不得低于10%
- 价格分应当采用低价优先法计算

**来源：** [财政部令第87号](http://www.mof.gov.cn)

### 财库46号（中小企业发展管理办法）

**中小企业声明函：**
- 格式标准：财库〔2020〕46号规定格式
- 优惠类型：价格扣除或评分加分
- 扣除比例：小微企业6%-10%

**来源：** [中国政府采购网](http://www.ccgp.gov.cn)

### 绿色产品认证评分规则

**市场监管总局规定：**
- 加分范围：2-5分
- 2026年起成为必要评分项
- 认证目录扩展至50大类产品

**来源：** [市场监管总局](https://www.samr.gov.cn)

---

**Stack research for:** 政府采购类型分类与政策性评分项
**Confidence:** HIGH - 法规依据明确，架构设计简洁