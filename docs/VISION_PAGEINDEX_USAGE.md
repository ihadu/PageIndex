# 扫描件PDF智能检索 - 使用指南

## 概述

本模块为 PageIndex 项目增加了扫描件PDF处理能力，使用 VLM（视觉语言模型）直接处理PDF图片，无需传统OCR。

## 核心特性

| 特性 | 说明 |
|------|------|
| **PDF转图片** | 使用PyMuPDF高质量提取PDF页面图片 |
| **VLM摘要生成** | 使用qwen-vl-plus为每页生成内容摘要 |
| **树结构索引** | 基于摘要构建层级索引，支持推理式检索 |
| **Agent检索** | 支持OpenAI Agents SDK进行智能检索 |
| **批量检索** | 针对采购文件场景的多要求批量检索 |

## 支持的模型

| 模型 | 用途 | 调用方式 |
|------|------|---------|
| **qwen-plus** | 文本推理、结构分析 | LiteLLM → 阿里云 |
| **qwen-vl-plus** | 图片处理、VLM摘要 | LiteLLM → 阿里云 |

## 安装依赖

```bash
# 核心依赖
pip install litellm pymupdf

# Agent支持（可选）
pip install openai-agents
```

## 配置API Key

### 方式一：环境变量

```bash
# 阿里云 DashScope API Key
export DASHSCOPE_API_KEY=your-api-key

# 或使用通用变量名
export OPENAI_API_KEY=your-api-key
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 方式二：代码中配置

```python
client = VisionPageIndexClient(
    api_key="your-dashscope-api-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
```

## 使用方式

### 方式一：一站式处理

```python
from pageindex import VisionPageIndexClient

# 初始化客户端
client = VisionPageIndexClient(
    text_model="qwen-plus",
    vision_model="qwen-vl-plus",
    api_key="your-api-key"
)

# 索引扫描件PDF
doc_id = client.index_scanned_pdf("响应文件.pdf")

# 检索
result = client.retrieve_with_vlm(doc_id, "查找技术方案设计说明")

print(f"定位页码: {result['page_ranges']}")
print(f"答案: {result['answer']}")
```

### 方式二：分步处理

```python
from pageindex import (
    extract_pdf_page_images,
    generate_page_summaries_batch,
    VisionPageIndexClient,
    answer_with_vlm
)
import asyncio

# Step 1: PDF转图片
page_images = extract_pdf_page_images("响应文件.pdf", "output_images")

# Step 2: VLM生成摘要
summaries = asyncio.run(generate_page_summaries_batch(
    page_images, model="qwen-vl-plus"
))

# Step 3: 初始化客户端并索引
client = VisionPageIndexClient()
doc_id = client.index_scanned_pdf("响应文件.pdf", generate_summaries=False)
client.page_summaries[doc_id] = summaries

# Step 4: 定位页码
result = client.retrieve_with_vlm(doc_id, "查找技术方案")

# Step 5: VLM生成答案
answer = asyncio.run(answer_with_vlm(
    "详细描述技术方案内容",
    result['image_paths']
))
```

### 方式三：Agent检索（需openai-agents）

```python
from pageindex import VisionPageIndexClient, create_vision_agent
from agents import Runner

client = VisionPageIndexClient()
doc_id = client.index_scanned_pdf("响应文件.pdf")

agent = create_vision_agent(client, doc_id)
result = Runner.run(agent, "查找项目实施计划")
```

### 方式四：工具函数方式

```python
from pageindex import VisionPageIndexClient, create_vision_agent_tools

client = VisionPageIndexClient()
doc_id = client.index_scanned_pdf("响应文件.pdf")

# 获取工具函数
tools = create_vision_agent_tools(client, doc_id)

# 直接调用
doc_info = tools['get_document']()
structure = tools['get_document_structure']()
content = tools['get_page_content']("5-7")
images = tools['get_page_images']("5-7")
```

## 采购文件场景示例

```python
from pageindex import (
    VisionPageIndexClient,
    batch_retrieve_for_requirements,
    generate_retrieval_report
)
import asyncio

# 定义采购要求
requirements = [
    "技术方案设计说明",
    "项目实施计划",
    "人员配置方案",
    "售后服务承诺",
    "资质证明材料",
]

# 初始化并索引
client = VisionPageIndexClient()
doc_id = client.index_scanned_pdf("响应文件.pdf")

# 批量检索
results = asyncio.run(batch_retrieve_for_requirements(
    client, doc_id, requirements
))

# 生成报告
report = generate_retrieval_report(results)
print(report)

# 保存报告
with open("检索报告.md", "w") as f:
    f.write(report)
```

## 核心API说明

### VisionPageIndexClient

```python
class VisionPageIndexClient:
    """
    支持扫描件PDF的增强客户端

    继承自 PageIndexClient，添加：
    - page_images: 页码→图片路径映射
    - page_summaries: 页码→摘要映射
    """

    def index_scanned_pdf(
        pdf_path: str,
        output_dir: str = None,      # 图片输出目录
        generate_summaries: bool = True  # 是否生成VLM摘要
    ) -> str:
        """索引扫描件PDF，返回doc_id"""

    def get_page_images(doc_id: str, pages: str) -> List[str]:
        """获取指定页码范围的图片路径"""

    def retrieve_with_vlm(
        doc_id: str,
        query: str,
        max_images: int = 5
    ) -> Dict:
        """
        使用VLM检索，返回：
        - page_ranges: 定位页码
        - image_paths: 图片路径
        - answer: VLM答案
        - verification: 满足度验证（如启用）
        """
```

### PDF图片提取

```python
def extract_pdf_page_images(
    pdf_path: str,
    output_dir: str = "pdf_images",
    zoom: float = 2.0,          # 放大倍数，提高质量
    image_format: str = "jpeg"  # 图片格式
) -> Dict[int, str]:
    """返回 {页码: 图片路径}"""
```

### VLM调用

```python
async def call_vlm_async(
    prompt: str,
    image_paths: List[str],
    model: str = "qwen-vl-plus"
) -> str:
    """异步调用VLM"""

def call_vlm(prompt: str, image_paths: List[str], model: str = "qwen-vl-plus") -> str:
    """同步调用VLM"""

async def answer_with_vlm(
    query: str,
    image_paths: List[str],
    model: str = "qwen-vl-plus"
) -> str:
    """使用VLM生成答案"""
```

### 批量检索

```python
async def batch_retrieve_for_requirements(
    client: VisionPageIndexClient,
    doc_id: str,
    requirements: List[str],
    max_images_per_req: int = 5
) -> List[Dict]:
    """
    批量检索多项采购要求

    返回每项要求的：
    - requirement: 原始要求
    - page_ranges: 定位页码
    - answer: VLM答案
    - verification: 满足度验证
    """

def generate_retrieval_report(results: List[Dict]) -> str:
    """生成Markdown格式报告"""
```

## 检索报告示例

```markdown
# 响应文件检索报告

## 1. 技术方案设计说明

**状态**: 满足

**定位页码**: 5-7

**已满足内容**: 包含完整的系统架构设计、技术选型说明...

**具体位置**: 第5-7页

---

## 2. 项目实施计划

**状态**: 部分满足

**定位页码**: 12-14

**已满足内容**: 包含时间安排和里程碑

**缺失内容**: 未包含风险应对措施

---

...
```

## 性能优化建议

1. **控制图片数量**: 每次查询建议不超过5张图片
2. **批量摘要生成**: 设置 `batch_size=5` 并发处理
3. **摘要缓存**: 预生成摘要后可复用
4. **图片质量**: `zoom=2.0` 平衡质量与大小

## 常见问题

### Q: 为什么扫描件无法用传统PageIndex？

传统PageIndex使用PyPDF2提取文本，扫描件PDF是图片，没有文本层。

### Q: VLM处理的成本如何？

qwen-vl-plus 每张图片约 0.002-0.008 元，取决于图片大小和模型版本。

### Q: 能处理多少页的PDF？

理论上无限，但建议单次检索不超过20页相关内容。

### Q: 如何处理超大PDF？

建议：
1. 预处理阶段生成所有图片和摘要
2. 使用workspace缓存索引结果
3. 分批检索，每次控制页码范围

## 运行示例

```bash
# 设置API Key
export DASHSCOPE_API_KEY=your-key

# 基础使用
python examples/example_vision_retrieval.py --pdf 响应文件.pdf --query "技术方案"

# 批量检索
python examples/example_vision_retrieval.py --pdf 响应文件.pdf --example 5

# 处理已有图片
python examples/example_vision_retrieval.py --image-dir output_images --query "总结内容"
```

## 更多资源

- [PageIndex GitHub](https://github.com/VectifyAI/PageIndex)
- [阿里云通义千问文档](https://help.aliyun.com/document_detail/2712195.html)
- [LiteLLM文档](https://docs.litellm.ai/)