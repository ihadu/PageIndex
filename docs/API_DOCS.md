# PageIndex HTTP API 接口文档

## 服务概述

PageIndex HTTP 服务提供文档索引和智能检索功能，支持异步任务处理。

**服务地址**：`http://localhost:8080`（可配置）

**协议**：HTTP/1.1，JSON 数据格式

**适用场景**：
- 上传 PDF 文件并创建索引
- 检索文档内容，定位评分项页码
- 管理 indexed 文档

---

## API 端点总览

| 端点 | 方法 | 功能 | 响应方式 |
|------|------|------|---------|
| `/health` | GET | 健康检查 | 同步 |
| `/index` | POST | 上传 PDF，创建索引任务 | 异步 |
| `/status/{task_id}` | GET | 查询任务状态和结果 | 同步 |
| `/retrieve` | POST | 检索文档内容 | 同步 |
| `/documents` | GET | 列出所有文档 | 同步 |
| `/documents/{doc_id}` | DELETE | 删除文档 | 同步 |
| `/supported_types` | GET | 获取支持的评分项类型 | 同步 |

---

## 1. 健康检查

### 请求

```
GET /health
```

### 响应

```json
{
    "status": "healthy",
    "timestamp": "2026-04-19T10:30:00",
    "queue_size": 0,
    "documents_count": 5
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态：`healthy` 或 `unhealthy` |
| `timestamp` | string | 当前时间（ISO 8601） |
| `queue_size` | integer | 当前任务队列大小 |
| `documents_count` | integer | 已索引文档数量 |

---

## 2. 创建索引任务

### 请求

```
POST /index
Content-Type: multipart/form-data
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file` | file | **必需** | PDF 文件 |
| `doc_name` | string | 可选 | 文档名称，默认为文件名 |
| `options` | string | 可选 | JSON 格式的索引选项 |

### options 参数说明

```json
{
    "generate_summaries": true,       // 是否生成 VLM 摘要（默认 true）
    "procurement_type": "服务类"       // 采购类型：货物类/服务类
}
```

### 请求示例

```bash
curl -X POST http://localhost:8080/index \
  -F "file=@响应文件.pdf" \
  -F "doc_name=项目响应文件" \
  -F 'options={"procurement_type":"服务类"}'
```

### 响应（成功）

```json
{
    "task_id": "task_abc123def456",
    "status": "pending",
    "message": "索引任务已创建",
    "estimated_time": "预计处理时间 1-5 分钟"
}
```

### 响应（队列满 - 503）

```json
{
    "success": false,
    "error": {
        "code": "QUEUE_FULL",
        "message": "服务繁忙，请稍后重试",
        "retry_after": 30
    }
}
```

### 响应（文件类型错误 - 400）

```json
{
    "success": false,
    "error": {
        "code": "INVALID_FILE_TYPE",
        "message": "仅支持 PDF 文件"
    }
}
```

---

## 3. 查询任务状态

### 请求

```
GET /status/{task_id}
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `task_id` | string | **必需** | 任务 ID（路径参数） |

### 响应（进行中）

```json
{
    "task_id": "task_abc123def456",
    "status": "processing",
    "created_at": "2026-04-19T10:30:00",
    "started_at": "2026-04-19T10:30:05",
    "progress": {
        "stage": "generating_summaries",
        "percent": 45,
        "message": "正在生成页面摘要..."
    }
}
```

### progress.stage 值说明

| 值 | 说明 | 进度范围 |
|------|------|------|
| `extracting_images` | 提取 PDF 页面图片 | 0-20% |
| `generating_summaries` | 生成 VLM 摘要 | 20-80% |
| `building_index` | 构建文档索引 | 80-95% |
| `finalizing` | 完成处理 | 95-100% |

### 响应（完成）

```json
{
    "task_id": "task_abc123def456",
    "status": "completed",
    "created_at": "2026-04-19T10:30:00",
    "started_at": "2026-04-19T10:30:05",
    "completed_at": "2026-04-19T10:35:00",
    "result": {
        "doc_id": "doc_xyz789abc123",
        "total_pages": 350,
        "indexed_pages": 350,
        "workspace_path": "./workspace/doc_xyz789abc123"
    }
}
```

### 响应（失败）

```json
{
    "task_id": "task_abc123def456",
    "status": "failed",
    "created_at": "2026-04-19T10:30:00",
    "completed_at": "2026-04-19T10:35:00",
    "error": {
        "code": "INDEX_FAILED",
        "message": "LLM API 调用超时"
    }
}
```

### status 值说明

| 值 | 说明 |
|------|------|
| `pending` | 任务在队列中等待 |
| `processing` | 任务正在处理 |
| `completed` | 任务完成，可检索 |
| `failed` | 任务失败 |

---

## 4. 检索文档内容

### 请求

```
POST /retrieve
Content-Type: application/json
```

### 参数

```json
{
    "doc_id": "doc_xyz789abc123",    // 必需：文档 ID
    "query": "人员配备在哪几页",        // 必需：查询内容
    "options": {                     // 可选：检索选项
        "max_images": 0,             // 最大图片数（默认 0，不调用 VLM）
        "procurement_type": "服务类"  // 采购类型过滤
    }
}
```

### options 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_images` | int | **0** | 最大图片数。0=仅返回页码范围，不调用 VLM；>0=调用 VLM 生成答案 |
| `procurement_type` | string | null | 采购类型过滤：`货物类` 或 `服务类` |

### 成本说明

| max_images | 功能 | 成本估算（300页文档） |
|------------|------|---------------------|
| **0（默认）** | 仅返回页码范围 | ~0.0001元/次（仅意图解析） |
| **5** | 调用 VLM 生成答案 | ~0.02元/次 |

### 请求示例

```bash
# 仅返回页码范围（推荐，成本最低）
curl -X POST http://localhost:8080/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc_xyz789abc123",
    "query": "人员配备在哪几页"
  }'

# 需要VLM答案时显式指定max_images
curl -X POST http://localhost:8080/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc_xyz789abc123",
    "query": "人员配备在哪几页",
    "options": {"max_images": 5}
  }'
```

### 响应（成功 - max_images=0）

```json
{
    "success": true,
    "result": {
        "requirement_type": "人员配备",
        "page_ranges": ["87-89"],
        "title_pages": [87],
        "material_pages": [88, 89],
        "material_details": [
            {"page": 88, "type": "操作证", "keywords_matched": ["操作手合格证"]},
            {"page": 89, "type": "健康证明", "keywords_matched": ["健康证明"]}
        ],
        "answer": "",
        "image_paths": []
    }
}
```

### 响应（成功 - max_images>0）

```json
{
    "success": true,
    "result": {
        "requirement_type": "人员配备",
        "page_ranges": ["87-89"],
        "title_pages": [87],
        "material_pages": [88, 89],
        "material_details": [
            {"page": 88, "type": "操作证", "keywords_matched": ["操作手合格证"]},
            {"page": 89, "type": "健康证明", "keywords_matched": ["健康证明"]}
        ],
        "answer": "人员配备证明材料位于第87-89页。第87页是人员配备章节标题页，第88页包含操作手合格证，第89页包含健康证明。",
        "image_paths": ["workspace/doc_xyz/images/page_87.jpg", ...]
    }
}
```

### result 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `requirement_type` | string | 匹配的评分项类型 |
| `page_ranges` | array[string] | 页码范围列表，格式如 `["87-89", "120-125"]` |
| `title_pages` | array[int] | 章节标题页页码 |
| `material_pages` | array[int] | 证明材料页页码 |
| `material_details` | array[object] | 每页材料详情 |
| `answer` | string | VLM 生成的自然语言答案 |

### 响应（文档不存在 - 404）

```json
{
    "success": false,
    "error": {
        "code": "DOC_NOT_FOUND",
        "message": "文档 doc_xyz789abc123 不存在"
    }
}
```

### 响应（检索失败 - 500）

```json
{
    "success": false,
    "error": {
        "code": "RETRIEVE_FAILED",
        "message": "VLM API 调用超时"
    }
}
```

---

## 5. 列出所有文档

### 请求

```
GET /documents
```

### 响应

```json
{
    "success": true,
    "documents": [
        {
            "doc_id": "doc_xyz789abc123",
            "doc_name": "项目响应文件",
            "total_pages": 350,
            "created_at": "2026-04-19T10:30:00"
        },
        {
            "doc_id": "doc_abc456def789",
            "doc_name": "采购文件",
            "total_pages": 120,
            "created_at": "2026-04-18T15:00:00"
        }
    ],
    "count": 2
}
```

---

## 6. 删除文档

### 请求

```
DELETE /documents/{doc_id}
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `doc_id` | string | **必需** | 文档 ID（路径参数） |

### 响应（成功）

```json
{
    "success": true,
    "message": "文档 doc_xyz789abc123 已删除"
}
```

### 响应（文档不存在 - 404）

```json
{
    "success": false,
    "error": {
        "code": "DOC_NOT_FOUND",
        "message": "文档 doc_xyz789abc123 不存在"
    }
}
```

---

## 7. 获取支持的评分项类型

### 请求

```
GET /supported_types
```

### 响应

```json
{
    "success": true,
    "types": [
        "人员配备",
        "类似业绩",
        "设备能力",
        "企业资质",
        "技术方案",
        "商务方案",
        "报价响应",
        "财务状况",
        "信誉荣誉",
        "中小企业声明函"
    ]
}
```

---

## 错误码总览

| HTTP 状态码 | 错误码 | 说明 | 处理建议 |
|-------------|--------|------|---------|
| 400 | `INVALID_FILE_TYPE` | 文件类型错误 | 仅支持 PDF |
| 400 | `INVALID_OPTIONS` | options JSON 格式错误 | 检查 JSON 格式 |
| 404 | `TASK_NOT_FOUND` | 任务不存在 | 检查 task_id |
| 404 | `DOC_NOT_FOUND` | 文档不存在 | 检查 doc_id |
| 500 | `TASK_CREATE_FAILED` | 任务创建失败 | 检查服务器日志 |
| 500 | `RETRIEVE_FAILED` | 检索失败 | LLM API 问题 |
| 503 | `QUEUE_FULL` | 队列已满 | 等待 retry_after 秒后重试 |

---

## 调用流程

### 完整流程：上传 → 索引 → 检索

```python
import httpx
import time

BASE_URL = "http://localhost:8080"

# 1. 上传文档
def upload_pdf(pdf_path: str, doc_name: str = None) -> str:
    """上传 PDF 并返回 doc_id"""
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path, f, "application/pdf")}
        data = {"doc_name": doc_name} if doc_name else {}
        
        resp = httpx.post(f"{BASE_URL}/index", files=files, data=data, timeout=30)
        
        if resp.status_code == 503:
            retry_after = resp.json()["error"]["retry_after"]
            raise Exception(f"服务繁忙，{retry_after}秒后重试")
        
        if resp.status_code != 200:
            raise Exception(f"上传失败: {resp.json()}")
        
        return resp.json()["task_id"]

# 2. 等待索引完成
def wait_for_index(task_id: str, max_wait: int = 300) -> str:
    """轮询任务状态，返回 doc_id"""
    start = time.time()
    
    while time.time() - start < max_wait:
        resp = httpx.get(f"{BASE_URL}/status/{task_id}", timeout=10)
        data = resp.json()
        
        if data["status"] == "completed":
            return data["result"]["doc_id"]
        
        if data["status"] == "failed":
            raise Exception(f"索引失败: {data['error']['message']}")
        
        # 可选：打印进度
        progress = data.get("progress", {})
        if progress:
            print(f"进度: {progress['percent']}%")
        
        time.sleep(5)
    
    raise Exception("索引超时")

# 3. 检索
def retrieve(doc_id: str, query: str, procurement_type: str = None) -> dict:
    """检索文档内容"""
    request = {
        "doc_id": doc_id,
        "query": query,
        "options": {"procurement_type": procurement_type} if procurement_type else {}
    }
    
    resp = httpx.post(f"{BASE_URL}/retrieve", json=request, timeout=60)
    
    if resp.status_code != 200:
        raise Exception(f"检索失败: {resp.json()}")
    
    return resp.json()["result"]

# 完整调用示例
task_id = upload_pdf("响应文件.pdf", "项目响应文件")
doc_id = wait_for_index(task_id)
result = retrieve(doc_id, "人员配备在哪几页", "服务类")

print(f"页码范围: {result['page_ranges']}")
print(f"答案: {result['answer']}")
```

---

## Python SDK 客户端

### 安装依赖

```bash
pip install httpx
```

### SDK 类封装

```python
"""
PageIndex HTTP 客户端 SDK

使用方式：
    client = PageIndexClient("http://localhost:8080")
    doc_id = client.upload_and_wait("响应文件.pdf")
    result = client.retrieve(doc_id, "人员配备在哪几页")
"""

import httpx
import time
from pathlib import Path
from typing import Optional, Dict, Any


class PageIndexClient:
    """PageIndex HTTP 服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        resp = httpx.get(f"{self.base_url}/health", timeout=5)
        return resp.json()
    
    def upload_pdf(
        self,
        pdf_path: str,
        doc_name: Optional[str] = None,
        procurement_type: Optional[str] = None
    ) -> str:
        """
        上传 PDF 文件
        
        Returns:
            task_id: 任务 ID
        """
        with open(pdf_path, "rb") as f:
            files = {"file": (Path(pdf_path).name, f, "application/pdf")}
            data = {}
            
            if doc_name:
                data["doc_name"] = doc_name
            
            if procurement_type:
                data["options"] = json.dumps({"procurement_type": procurement_type})
            
            resp = httpx.post(
                f"{self.base_url}/index",
                files=files,
                data=data,
                timeout=self.timeout
            )
            
            if resp.status_code == 503:
                error = resp.json()["error"]
                raise ServiceBusyError(error["retry_after"])
            
            if resp.status_code != 200:
                raise APIError(resp.json()["error"])
            
            return resp.json()["task_id"]
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        resp = httpx.get(f"{self.base_url}/status/{task_id}", timeout=10)
        
        if resp.status_code == 404:
            raise TaskNotFoundError(task_id)
        
        return resp.json()
    
    def wait_for_index(
        self,
        task_id: str,
        max_wait: int = 300,
        poll_interval: int = 5,
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        等待索引完成
        
        Args:
            task_id: 任务 ID
            max_wait: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
            progress_callback: 进度回调函数
        
        Returns:
            doc_id: 文档 ID
        """
        start = time.time()
        
        while time.time() - start < max_wait:
            data = self.get_task_status(task_id)
            
            if data["status"] == "completed":
                return data["result"]["doc_id"]
            
            if data["status"] == "failed":
                raise IndexFailedError(data["error"]["message"])
            
            if progress_callback and "progress" in data:
                progress_callback(data["progress"])
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"索引超时（超过 {max_wait} 秒）")
    
    def upload_and_wait(
        self,
        pdf_path: str,
        doc_name: Optional[str] = None,
        procurement_type: Optional[str] = None,
        max_wait: int = 300
    ) -> str:
        """
        上传并等待索引完成（便捷方法）
        
        Returns:
            doc_id: 文档 ID
        """
        task_id = self.upload_pdf(pdf_path, doc_name, procurement_type)
        return self.wait_for_index(task_id, max_wait)
    
    def retrieve(
        self,
        doc_id: str,
        query: str,
        max_images: int = 0,  # 默认不调用 VLM，仅返回页码范围
        procurement_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        检索文档内容
        
        Args:
            doc_id: 文档 ID
            query: 查询内容
            max_images: 最大图片数（默认 0，不调用 VLM）
            procurement_type: 采购类型过滤
        
        Returns:
            result: 检索结果（max_images=0时仅返回页码，max_images>0时返回VLM答案）
        """
        request = {
            "doc_id": doc_id,
            "query": query,
            "options": {"max_images": max_images}
        }
        
        if procurement_type:
            request["options"]["procurement_type"] = procurement_type
        
        resp = httpx.post(
            f"{self.base_url}/retrieve",
            json=request,
            timeout=60
        )
        
        if resp.status_code == 404:
            raise DocNotFoundError(doc_id)
        
        if resp.status_code != 200:
            raise APIError(resp.json()["error"])
        
        return resp.json()["result"]
    
    def list_documents(self) -> list:
        """列出所有文档"""
        resp = httpx.get(f"{self.base_url}/documents", timeout=10)
        return resp.json()["documents"]
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        resp = httpx.delete(f"{self.base_url}/documents/{doc_id}", timeout=10)
        return resp.status_code == 200
    
    def get_supported_types(self) -> list:
        """获取支持的评分项类型"""
        resp = httpx.get(f"{self.base_url}/supported_types", timeout=10)
        return resp.json()["types"]


# 异常类
class ServiceBusyError(Exception):
    """服务繁忙异常"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"服务繁忙，{retry_after}秒后重试")


class APIError(Exception):
    """API 错误"""
    def __init__(self, error: dict):
        self.code = error["code"]
        self.message = error["message"]
        super().__init__(f"{self.code}: {self.message}")


class TaskNotFoundError(Exception):
    """任务不存在"""
    pass


class DocNotFoundError(Exception):
    """文档不存在"""
    pass


class IndexFailedError(Exception):
    """索引失败"""
    pass


# 使用示例
if __name__ == "__main__":
    import json
    
    client = PageIndexClient("http://localhost:8080")
    
    # 健康检查
    print("服务状态:", client.health_check())
    
    # 上传并索引
    doc_id = client.upload_and_wait("响应文件.pdf", "项目响应文件")
    print(f"文档 ID: {doc_id}")
    
    # 检索
    result = client.retrieve(doc_id, "人员配备在哪几页")
    print(f"页码: {result['page_ranges']}")
    print(f"答案: {result['answer']}")
    
    # 删除
    client.delete_document(doc_id)
```

---

## 处理时间参考

| 文档规模 | 页数 | 索引时间 | 建议超时设置 |
|---------|------|---------|-------------|
| 小型 | <50 | 30秒 | 60秒 |
| 中型 | 50-200 | 1-2分钟 | 180秒 |
| 大型 | 200-500 | 2-5分钟 | 300秒 |
| 超大 | >500 | 5分钟+ | 600秒 |

---

## 并发限制

| 参数 | 值 | 说明 |
|------|------|------|
| `max_concurrent_tasks` | 5 | 同时处理的任务数 |
| `task_queue_size` | 10 | 队列最大长度 |

超过限制时返回 `503 QUEUE_FULL`，建议等待 `retry_after` 秒后重试。

---

## 版本

文档版本：v1.4

更新日期：2026-04-19

---

## 模型配置

### 默认模型（qwen3 系列）

| 模型类型 | 默认值 | 提供商 | 价格（输入/M | 输出/M） |
|----------|--------|--------|----------------------|
| **文本模型** | `qwen3.5-flash` | 阿里云 DashScope | 0.2元 | 2元 |
| **视觉模型** | `qwen3-vl-flash` | 阿里云 DashScope | 0.15元 | 1.5元 |

### 成本估算

| 操作 | Token消耗 | 成本估算 |
|------|----------|---------|
| 索引（300页） | 450K输入 + 30K输出 | ~0.11元 |
| 检索（max_images=0） | 300输入 + 100输出 | ~0.0001元 |
| 检索（max_images=5） | 7.5K输入 + 1.5K输出 | ~0.02元 |

### 配置方式

服务启动时通过环境变量或配置文件指定：

```bash
# 环境变量
export DASHSCOPE_API_KEY=your-api-key
export TEXT_MODEL=qwen3.5-flash
export VISION_MODEL=qwen3-vl-flash
```

```python
# 配置文件（config.yaml）
llm:
  text_model: "qwen3.5-flash"
  vision_model: "qwen3-vl-flash"
  api_key: "${DASHSCOPE_API_KEY}"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```