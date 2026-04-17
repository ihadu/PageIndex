# PageIndex 端到端测试指南

## 测试目标

验证 PageIndex 对包含大量扫描件的投标文件的处理准确性，特别是：
- 搜索"类似业绩"、"设备能力"、"人员配备"等评分项的页码范围
- 验证生成的文档结构索引是否准确

## 前置条件

### 1. 安装依赖

```bash
cd /Users/mac/work/PageIndex-clean

# 基础依赖（已有）
pip install -r requirements.txt

# 端到端测试额外依赖
pip install pdf2image requests

# pdf2image 需要系统安装 poppler
# macOS:
brew install poppler

# Linux:
apt-get install poppler-utils
```

### 2. 配置 API Key

使用阿里云灵积 API（推荐，支持 Qwen 模型）：

```bash
# 设置阿里云灵积 API Key
export DASHSCOPE_API_KEY="your_dashscope_api_key"

# 或者在 .env 文件中配置
echo "DASHSCOPE_API_KEY=your_key" > /Users/mac/work/PageIndex-clean/.env
```

**获取 API Key：**
- 访问 https://dashscope.console.aliyun.com/
- 创建 API Key
- qwen-plus 和 qwen-vl-plus 都在灵积平台可用

### 3. 验证测试文件

```bash
# 确认测试文件存在
ls -la "/Users/mac/work/tender-bid-analysis/docs/2026年小麦一喷三防飞防服务/安徽露一手智能科技有限公司/04整本响应文件.pdf"
```

## 测试方案

### 方案 A: 使用 qwen-plus（文本模型）

适合 OCR 效果好的文档，速度较快。

```bash
cd /Users/mac/work/PageIndex-clean

# 运行端到端测试
python tests/e2e_test_pageindex.py --model qwen-plus
```

**注意：** qwen-plus 是纯文本模型，对于扫描件，PageIndex 会使用 PyPDF2/pymupdf 进行文本提取，OCR 效果可能不佳。

### 方案 B: 使用 qwen-vl-plus（视觉模型）- 推荐

直接处理扫描件图片，准确率更高。

```bash
cd /Users/mac/work/PageIndex-clean

# 运行扫描件分析
python tests/scanned_pdf_analyzer.py

# 或指定特定页码范围
python tests/scanned_pdf_analyzer.py --pages "1-50"
```

### 方案 C: 混合方案（最佳）

1. 先用 PageIndex 生成文档结构索引
2. 用视觉模型验证关键页面的内容

```bash
# 1. 生成索引
python tests/e2e_test_pageindex.py --model qwen-plus

# 2. 验证关键页面
python tests/scanned_pdf_analyzer.py --pages "关键页码范围"
```

## 预期输出

### 端到端测试输出

```
PageIndex 端到端测试
============================================================
[设置] 使用模型: qwen-plus (openai/qwen-plus)
[索引] 开始处理文档: 04整本响应文件.pdf
[索引] 文件页数: XX
[索引] 完成索引，耗时: XX秒
[索引] 文档ID: xxx-xxx-xxx

[结构] 文档树结构:
============================================================
[节点ID] 标题 — 摘要...
============================================================

[搜索] 搜索评分项关键词...
[搜索] 关键词: '类似业绩'
  - 找到匹配: XX章节
    页码范围: X - X
...
```

### 扫描件分析输出

```
扫描件 PDF 分析
使用 qwen-vl-plus 视觉模型
============================================================
[扫描] PDF 总页数: XX
[转换] 将 PDF 第1-XX页转换为图片...
[分析] 分析第 X 页...
  第X页: 发现关键词 ['类似业绩']

[结果摘要]
  类似业绩: 第 X-X 页
  设备能力: 第 X-X 页
  人员配备: 第 X-X 页
```

## 结果文件

测试结果保存在 `/Users/mac/work/PageIndex-clean/tests/results/` 目录：

- `e2e_test_YYYYMMDD_HHMMSS.json` - 端到端测试结果
- `scanned_pdf_analysis_YYYYMMDD_HHMMSS.json` - 扫描件分析结果

## 验证方法

### 1. 人工对比验证

将系统输出的页码范围与人工标注对比：

```python
import json

# 读取测试结果
with open('tests/results/e2e_test_XXX.json', 'r') as f:
    result = json.load(f)

# 查看关键词匹配
for keyword, info in result['search_results'].items():
    print(f"{keyword}: {info}")
```

### 2. 页面内容验证

检查系统定位的页面是否确实包含关键词：

```python
from pageindex import PageIndexClient

client = PageIndexClient(workspace='tests/workspace')
content = client.get_page_content(doc_id, "5-7")

# 检查关键词
if "类似业绩" in content:
    print("验证成功")
```

### 3. 视觉验证（扫描件）

使用视觉模型二次验证：

```python
from tests.scanned_pdf_analyzer import ScannedPDFAnalyzer

analyzer = ScannedPDFAnalyzer()
# 验证特定页面
analyzer.analyze_page_with_vision('tests/image_cache/page_5.png', 5)
```

## 常见问题

### Q1: API Key 配置错误

```
错误: 需要设置 API Key
解决: export DASHSCOPE_API_KEY=your_key
```

### Q2: pdf2image 转换失败

```
错误: PDFInfoNotInstalledError
解决: brew install poppler (macOS)
```

### Q3: 扫描件 OCR 效果差

```
症状: PyPDF2 提取的文本为空或乱码
解决: 使用 qwen-vl-plus 视觉模型（方案 B）
```

### Q4: API 请求超时

```
症状: requests.exceptions.Timeout
解决: 
1. 检查网络连接
2. 减少单次处理的页面数量
3. 增加超时时间 timeout=120
```

## 测试指标

### 准确性指标

- **召回率**: 找到的评分项占实际评分项的比例
- **精确率**: 正确定位的评分项比例
- **页码准确性**: 定位的页码范围是否覆盖实际内容

### 效率指标

- **处理时间**: 总处理时间
- **单页处理时间**: 平均每页处理时间
- **API 调用次数**: 总 API 调用次数

## 扩展测试

可以添加更多评分项关键词：

```python
# 在测试脚本中添加
SCORE_KEYWORDS = [
    "类似业绩",
    "设备能力",
    "人员配备",
    "企业资质",
    "技术方案",
    # 添加更多...
]
```

## 下一步

1. 运行测试并收集结果
2. 对比人工标注验证准确性
3. 根据结果调整模型和参数
4. 生成测试报告