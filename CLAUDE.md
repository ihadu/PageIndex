# PageIndex 项目开发指南

## 项目概述

PageIndex 是一个 **向量无关、基于推理的 RAG 系统**，用于长文档的智能检索。

核心特点：
- 无向量数据库：使用文档结构和 LLM 推理进行检索
- 无分块：文档组织为自然章节
- 人类式检索：模拟专家导航和提取知识的方式

### v1.1 新增特性

- **采购类型分类**：货物类/服务类区分，评分项按类型适用
- **权重差异化配置**：符合财政部87号令（货物价格30-50分，服务10-30分）
- **政策性评分项**：中小企业声明函识别，符合财库〔2020〕46号
- **API向后兼容**：所有新增参数使用默认值，现有调用无需修改

## 核心模块

### 1. PageIndex 树结构索引 (`pageindex/page_index.py`)
- 从 PDF 生成层级树结构（类似目录）
- 支持节点 ID、摘要、描述

### 2. VisionPageIndex 视觉检索 (`pageindex/vision_pageindex.py`)
- **扫描件 PDF 检索**：直接处理 PDF 页面图片
- **多轮扩展检索**：标题页 + 证明材料页自动合并
- **OpenAI Agents SDK 集成**：支持 Chat Completions API
- **工作区持久化**：索引缓存避免重复生成

### 3. 采购评分项知识库 (`pageindex/procurement_knowledge.py`)

v1.1 增强功能：
- **采购类型分类**：`ProcurementType` 枚举（货物类/服务类）
- **类型配置**：`PROCUREMENT_TYPE_KNOWLEDGE` 存储类型权重范围
- **10种评分项**：人员配备、类似业绩、设备能力、企业资质、技术方案、商务方案、报价响应、财务状况、信誉荣誉、中小企业声明函
- **权重差异化**：`weight_range` 字段按类型配置权重范围
- **标题关键词 + 证明材料关键词映射**
- **排除关键词机制**：过滤偏离表等

新增方法：
- `get_procurement_type_config()`: 获取类型配置
- `get_requirements_for_type()`: 获取类型适用评分项
- `get_weight_info()`: 获取权重范围
- `validate_weights()`: 验证权重配置合规
- `get_policy_requirements()`: 获取政策性评分项
- `check_policy_compliance()`: 政策合规检查

### 4. 知识库构建工具 (`pageindex/procurement_kb_builder.py`)
- `TenderParser`：从采购文件提取评分项
- `KeywordDiscovery`：从摘要发现新关键词
- `KBValidator`：验证知识库准确性
- `KBManager`：版本管理、合并、导出
- `ExpertKBEnricher`：专家知识注入

## 快速使用

### 基础树结构索引

```bash
pip install -r requirements.txt
python run_pageindex.py --pdf_path /path/to/document.pdf
```

### 扫描件 PDF 检索（采购响应文件）

```python
from pageindex.vision_pageindex import VisionPageIndexClient
from pageindex.procurement_knowledge import ProcurementType

# 创建客户端（workspace 持久化索引）
client = VisionPageIndexClient(
    model="qwen-plus",
    workspace="./workspace"
)

# 索引响应文件
doc_id = client.create_vision_index(
    pdf_path="响应文件.pdf",
    doc_name="项目响应文件"
)

# 扩展检索（推荐）
result = client.retrieve_with_expansion(doc_id, "人员配备")
# 输出：87-89页（标题页87 + 证明材料页88-89）

# v1.1 新增：按采购类型过滤检索
result = client.retrieve_with_expansion(
    doc_id, "设备能力", 
    procurement_type="货物类"  # 仅检索货物类评分项
)
```

### 采购类型分类使用（v1.1）

```python
from pageindex.procurement_knowledge import ProcurementKnowledgeBase, ProcurementType

kb = ProcurementKnowledgeBase()

# 查看采购类型
print(kb.get_all_procurement_types())  # [GOODS, SERVICES]

# 查看类型关键评分项
print(kb.get_requirements_for_type(ProcurementType.GOODS))  # ['设备能力', '企业资质', '报价响应']
print(kb.get_requirements_for_type(ProcurementType.SERVICES))  # ['人员配备', '类似业绩', '技术方案']

# 查看权重差异（财政部87号令）
print(kb.get_weight_info("报价响应", ProcurementType.GOODS))  # {'min': 30, 'max': 50}
print(kb.get_weight_info("报价响应", ProcurementType.SERVICES))  # {'min': 10, 'max': 30}

# 验证权重配置
config = {"报价响应": 20, "技术方案": 30, "人员配备": 15, ...}
result = kb.validate_weights(ProcurementType.SERVICES, config)
print(result["is_valid"])  # True/False
```

### 政策性评分项使用（v1.1）

```python
# 查看政策性评分项
print(kb.get_policy_requirements())  # ['中小企业声明函']

# 查看政策详情
print(kb.get_policy_info("中小企业声明函"))
# {'policy_type': '中小企业扶持', 'policy_reference': '财库〔2020〕46号', ...}

# 政策合规检查
print(kb.check_policy_compliance("中小企业声明函"))
# {'is_policy': True, 'compliance_notes': ['小微企业享受6-10%价格扣除优惠', ...]}
```

### Agent 检索（OpenAI Agents SDK）

```python
from pageindex.vision_pageindex import create_vision_agent

# 创建 Agent
agent = create_vision_agent(
    client=client,
    doc_id=doc_id,
    agent_model="qwen-plus"
)

# 运行检索
from agents import Runner
result = Runner.run(agent, "查询人员配备在哪几页")
```

## 配置要求

### 环境变量

```bash
# LLM API（支持 LiteLLM 格式）
OPENAI_API_KEY=your_key          # OpenAI
DASHSCOPE_API_KEY=your_key       # 阿里云 DashScope

# 可选：自定义 API 地址
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 模型配置

```python
# 使用阿里云 DashScope
client = VisionPageIndexClient(
    model="qwen-plus",           # 文本模型
    vlm_model="qwen-vl-plus",    # 视觉模型
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 使用 OpenAI
client = VisionPageIndexClient(
    model="gpt-4o",
    vlm_model="gpt-4o-mini"
)
```

## 采购评分项知识库原理

### 核心问题

响应文件采用 **"标题页 + 证明材料页"** 结构：
- 标题页包含评分项关键词（如"人员配备")
- 证明材料页不含评分项关键词（如操作证、合同）

传统关键词检索会漏检证明材料页。

### v1.1 类型分类原理

财政部87号令规定货物类和服务类评分权重不同：

| 采购类型 | 价格权重 | 关键评分项 |
|---------|---------|-----------|
| 货物类 | 30-50% | 设备能力、报价响应、企业资质 |
| 服务类 | 10-30% | 人员配备、技术方案、类似业绩 |

知识库按类型配置：
```python
"报价响应": {
    "procurement_types": [GOODS, SERVICES],  # 通用
    "weight_range": {
        GOODS: {"min": 30, "max": 50},
        SERVICES: {"min": 10, "max": 30}
    }
}

"人员配备": {
    "procurement_types": [SERVICES],  # 服务类专用
    "weight_range": {
        SERVICES: {"min": 10, "max": 25}
    }
}
```

### 解决方案

知识库记录评分项与证明材料的映射：

```json
{
  "人员配备": {
    "procurement_types": ["服务类"],
    "weight_range": {"服务类": {"min": 10, "max": 25}},
    "title_keywords": ["人员配备", "人员配置"],
    "material_types": {
      "操作证": {"keywords": ["操作手合格证", "无人机操作证"]},
      "健康证明": {"keywords": ["健康证", "体检证明"]}
    }
  }
}
```

检索流程：
1. 定位标题页（搜索评分项关键词）
2. 扫描证明材料页（搜索材料关键词）
3. 合并完整范围
4. （v1.1新增）按采购类型过滤

### 扩展检索 API

```python
result = client.retrieve_with_expansion(doc_id, "人员配备")

# 返回结构
{
    "requirement_type": "人员配备",
    "page_ranges": ["87-89"],       # 完整范围
    "title_pages": [87],            # 标题页
    "material_pages": [88, 89],     # 证明材料页
    "material_details": [
        {"page": 88, "type": "操作证"},
        {"page": 89, "type": "健康证明"}
    ]
}
```

## 开发经验

### 1. LiteLLM 模型名称格式

LiteLLM 要求模型名称带 provider 前缀：
- OpenAI: `model="gpt-4o"` 或 `model="openai/gpt-4o"`
- 阿里云: `model="openai/qwen-plus"` + `base_url`

**注意**: OpenAI Agents SDK 会自动添加 `openai/` 前缀，需要在 `create_vision_agent` 中剥离。

### 2. 工作区持久化

VisionPageIndexClient 使用 workspace 目录缓存：
- `page_summaries.json`: 页面摘要
- `doc_structure.json`: 文档结构
- `page_images/`: 页面图片

避免每次重新生成摘要（耗时约 1 分钟/100 页）。

### 3. Agent 模型兼容

阿里云 DashScope 使用 Chat Completions API，需要：

```python
from pageindex.vision_pageindex import create_chat_completions_model_provider

model_provider = create_chat_completions_model_provider(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
```

### 4. 关键词发现流程

从历史响应文件发现新关键词：

```python
from pageindex.procurement_kb_builder import KeywordDiscovery

discovery = KeywordDiscovery(kb)
result = discovery.discover_from_summaries(
    page_summaries={87: "...", 88: "..."},
    requirement_type="人员配备"
)

# 发现新关键词如 "大疆认证"、"飞手资质证书"
# 自动补充到知识库
```

## 文件结构

```
pageindex/
├── page_index.py           # 树结构索引
├── vision_pageindex.py     # 视觉检索 + Agent（v1.1 支持类型参数）
├── procurement_knowledge.py # 评分项知识库（v1.1 类型分类 + 权重配置）
├── procurement_kb_builder.py # 知识库构建工具
├── client.py               # API 客户端
├── retrieve.py             # 检索函数
└── utils.py                # 工具函数

docs/
├── VISION_PAGEINDEX_USAGE.md    # 视觉检索使用指南
├── PROCUREMENT_KB_BUILDING.md   # 知识库企业落地方案
├── PROCUREMENT_KB_EVALUATION.md # v1.1 系统评估（评分 6.8）

examples/
├── example_vision_retrieval.py  # Agent 检索示例
├── agentic_vectorless_rag_demo.py

tests/
├── test_procurement_kb.py       # 知识库测试
├── test_procurement_type.py     # v1.1 类型分类测试（62个）
```

## 常见问题

### Q: 为什么检索不到证明材料页？

A: 证明材料页不含评分项关键词。使用 `retrieve_with_expansion()` 方法，知识库会自动搜索材料关键词。

### Q: 模型调用报错 "model does not exist"？

A: 检查模型名称格式和 base_url 配置。阿里云需要设置正确的 base_url。

### Q: 如何按采购类型过滤检索？（v1.1）

A: 使用 `procurement_type` 参数：
```python
# 仅检索货物类评分项
result = client.retrieve_with_expansion(doc_id, "设备", procurement_type="货物类")

# 仅检索服务类评分项
result = client.retrieve_with_expansion(doc_id, "人员", procurement_type="服务类")
```

### Q: 如何验证权重配置是否符合87号令？（v1.1）

A: 使用 `validate_weights()` 方法：
```python
config = {"报价响应": 20, "技术方案": 30, "人员配备": 15, ...}
result = kb.validate_weights(ProcurementType.SERVICES, config)
if not result["is_valid"]:
    print("问题:", result["issues"])
```

### Q: 如何检测中小企业声明函？（v1.1）

A: 使用政策性评分项方法：
```python
# 检索中小企业声明函
result = client.retrieve_with_expansion(doc_id, "中小企业声明函")

# 获取政策信息
info = kb.get_policy_info("中小企业声明函")
print("价格扣除:", info["price_deduction_range"])  # 6-10%
```

### Q: 如何添加新的评分项类型？

A: 使用 `ExpertKBEnricher`：

```python
enricher.add_material_type(
    "人员配备",
    "新证明材料",
    ["关键词1", "关键词2"]
)
```

## 相关文档

- [视觉检索使用指南](docs/VISION_PAGEINDEX_USAGE.md)
- [知识库企业落地方案](docs/PROCUREMENT_KB_BUILDING.md)
- [系统评估文档](docs/PROCUREMENT_KB_EVALUATION.md) - v1.1 综合评分 6.8
- [PageIndex 官方文档](https://docs.pageindex.ai)

---

**版本记录：**
- v1.0: 基础知识库（9种评分项）
- v1.1: 类型分类 + 权重差异化 + 政策性评分项（2026-04-17）