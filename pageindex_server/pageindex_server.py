"""
PageIndex HTTP 服务

提供 REST API 用于：
- 上传 PDF 文件并创建索引（异步任务）
- 查询任务状态和结果
- 检索文档内容
- 删除文档

部署方式：
- Docker 容器化
- Docker Compose
- Kubernetes（可选）

启动命令：
    uvicorn pageindex_server:app --host 0.0.0.0 --port 8080
"""

import os
import sys
import json
import uuid
import asyncio
import tempfile
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 导入
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import yaml

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入 PageIndex 核心模块
try:
    from pageindex.vision_pageindex import VisionPageIndexClient, extract_pdf_page_images
    from pageindex.procurement_knowledge import ProcurementKnowledgeBase, ProcurementType
    from pageindex_server.task_manager import TaskManager, TaskStatus, TaskStage
except ImportError as e:
    logger.error(f"导入失败: {e}")
    raise

# ============== 配置加载 ==============

def load_config() -> Dict[str, Any]:
    """加载服务配置"""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        # 默认配置
        config = {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "max_concurrent_tasks": 5,
                "task_queue_size": 10
            },
            "llm": {
                "text_model": "qwen3.5-flash",
                "vision_model": "qwen3-vl-flash",
                "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "timeout": 60,
                "retry": 2
            },
            "workspace": {
                "path": os.getenv("WORKSPACE_PATH", "./workspace"),
                "auto_cleanup_days": 7
            }
        }

    # 替换环境变量
    if "${DASHSCOPE_API_KEY}" in str(config.get("llm", {}).get("api_key", "")):
        config["llm"]["api_key"] = os.getenv("DASHSCOPE_API_KEY", "")

    return config


CONFIG = load_config()

# ============== Pydantic 模型 ==============

class RetrieveRequest(BaseModel):
    """检索请求"""
    doc_id: str = Field(..., description="文档 ID")
    query: str = Field(..., description="查询内容")
    options: Optional[Dict[str, Any]] = Field(default=None, description="检索选项")


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: Dict[str, Any]


# ============== FastAPI 应用 ==============

app = FastAPI(
    title="PageIndex HTTP 服务",
    description="向量无关、基于推理的 RAG 系统 HTTP API",
    version="1.0.0"
)

# 任务管理器（全局实例）
task_manager: Optional[TaskManager] = None

# VisionPageIndexClient（全局实例）
vision_client: Optional[VisionPageIndexClient] = None

# ProcurementKnowledgeBase（全局实例）
procurement_kb: Optional[ProcurementKnowledgeBase] = None


@app.on_event("startup")
async def startup_event():
    """启动事件：初始化服务"""
    global task_manager, vision_client, procurement_kb

    logger.info("启动 PageIndex HTTP 服务...")

    # 初始化 VisionPageIndexClient
    vision_client = VisionPageIndexClient(
        text_model=CONFIG["llm"]["text_model"],
        vision_model=CONFIG["llm"]["vision_model"],
        api_key=CONFIG["llm"]["api_key"],
        base_url=CONFIG["llm"]["base_url"],
        workspace=CONFIG["workspace"]["path"]
    )
    logger.info(f"VisionPageIndexClient 初始化完成: {CONFIG['llm']['text_model']}")

    # 初始化 ProcurementKnowledgeBase
    procurement_kb = ProcurementKnowledgeBase()
    logger.info("ProcurementKnowledgeBase 初始化完成")

    # 初始化任务管理器
    task_manager = TaskManager(
        max_concurrent_tasks=CONFIG["server"]["max_concurrent_tasks"],
        queue_size=CONFIG["server"]["task_queue_size"],
        workspace_path=CONFIG["workspace"]["path"],
        index_handler=index_handler
    )

    # 启动 Worker
    await task_manager.start()
    logger.info(f"任务管理器启动: {CONFIG['server']['max_concurrent_tasks']} Workers")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件：清理资源"""
    global task_manager

    logger.info("关闭 PageIndex HTTP 服务...")

    if task_manager:
        await task_manager.stop()

    logger.info("服务已关闭")


# ============== 索引处理函数 ==============

async def index_handler(
    params: Dict[str, Any],
    progress_callback: callable
) -> Dict[str, Any]:
    """
    索引处理函数

    Args:
        params: 任务参数
            - file_path: PDF 文件路径
            - doc_name: 文档名称
            - options: 索引选项
        progress_callback: 进度回调函数

    Returns:
        索引结果
            - doc_id: 文档 ID
            - total_pages: 总页数
            - indexed_pages: 已索引页数
    """
    file_path = params["file_path"]
    doc_name = params.get("doc_name", Path(file_path).stem)
    options = params.get("options", {})

    # 生成文档 ID（使用完整 UUID 格式，与 VisionPageIndexClient 一致）
    doc_id = str(uuid.uuid4())

    # 阶段 1: 提取图片
    progress_callback(TaskStage.EXTRACTING_IMAGES, 10, "正在提取 PDF 页面图片...")
    output_dir = Path(CONFIG["workspace"]["path"]) / doc_id / "page_images"
    output_dir.mkdir(parents=True, exist_ok=True)

    page_images = extract_pdf_page_images(
        pdf_path=file_path,
        output_dir=str(output_dir),
        zoom=2.0
    )
    total_pages = len(page_images)
    logger.info(f"提取 {total_pages} 页图片")

    # 阶段 2: 生成摘要
    progress_callback(TaskStage.GENERATING_SUMMARIES, 30, "正在生成页面摘要...")

    generate_summaries = options.get("generate_summaries", True)
    if generate_summaries:
        # 使用 VisionPageIndexClient 创建索引
        # 注意: 这里需要同步调用异步方法
        # 在 Worker 协程中可以直接使用 await
        pass  # 实际由 VisionPageIndexClient 内部处理

    # 阶段 3: 构建索引
    progress_callback(TaskStage.BUILDING_INDEX, 60, "正在构建文档索引...")

    # 使用 VisionPageIndexClient 创建索引
    # 由于当前实现是同步的，我们使用临时方案
    try:
        # 复制文件到 workspace
        doc_workspace = Path(CONFIG["workspace"]["path"]) / doc_id
        doc_workspace.mkdir(parents=True, exist_ok=True)

        # 保存元数据
        metadata = {
            "doc_id": doc_id,
            "doc_name": doc_name,
            "total_pages": total_pages,
            "file_path": file_path,
            "created_at": datetime.now().isoformat(),
            "options": options
        }
        with open(doc_workspace / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 创建 PageIndexClient 索引（如果启用摘要生成）
        if generate_summaries:
            # 这里需要调用 vision_client 的方法
            # 由于 vision_client 的方法是同步的，我们在线程中执行
            loop = asyncio.get_event_loop()

            def create_index():
                return vision_client.get_or_create_index(
                    pdf_path=file_path,
                    output_dir=str(output_dir),
                    force_reindex=True,
                    doc_id=doc_id  # 传递 HTTP层生成的 doc_id
                )

            # 在线程池中执行
            actual_doc_id = await loop.run_in_executor(None, create_index)

            # 验证 doc_id 一致性
            if actual_doc_id != doc_id:
                logger.warning(f"doc_id不一致: HTTP层={doc_id}, Vision层={actual_doc_id}")
                # 使用 VisionClient 返回的实际 doc_id
                doc_id = actual_doc_id

            # 更新进度
            progress_callback(TaskStage.BUILDING_INDEX, 80, "索引构建完成...")

    except Exception as e:
        logger.error(f"索引构建失败: {e}")
        raise RuntimeError(f"索引构建失败: {e}")

    # 阶段 4: 完成
    progress_callback(TaskStage.FINALIZING, 100, "索引完成")

    return {
        "doc_id": doc_id,
        "total_pages": total_pages,
        "indexed_pages": total_pages,
        "workspace_path": str(doc_workspace)
    }


# ============== API 端点 ==============

@app.get("/health")
async def health_check():
    """
    健康检查

    检查服务状态和依赖组件。
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "queue_size": task_manager.get_queue_size() if task_manager else 0,
        "documents_count": len(task_manager.list_documents()) if task_manager else 0
    }


@app.post("/index")
async def create_index(
    file: UploadFile = File(...),
    doc_name: Optional[str] = Form(default=None),
    options: Optional[str] = Form(default=None)
):
    """
    创建索引任务

    上传 PDF 文件，创建异步索引任务。

    Args:
        file: PDF 文件
        doc_name: 文档名称（可选）
        options: 索引选项 JSON（可选）

    Returns:
        task_id: 任务 ID
        status: 任务状态
    """
    # 检查队列是否已满
    if task_manager.is_queue_full():
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "QUEUE_FULL",
                    "message": "服务繁忙，请稍后重试",
                    "retry_after": 30
                }
            }
        )

    # 验证文件类型
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "仅支持 PDF 文件"
                }
            }
        )

    # 保存临时文件
    temp_dir = tempfile.mkdtemp()
    temp_file = Path(temp_dir) / file.filename

    try:
        # 写入临时文件
        content = await file.read()
        with open(temp_file, "wb") as f:
            f.write(content)

        # 解析选项
        options_dict = {}
        if options:
            try:
                options_dict = json.loads(options)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": {
                            "code": "INVALID_OPTIONS",
                            "message": "options 参数必须是有效的 JSON"
                        }
                    }
                )

        # 创建任务
        params = {
            "file_path": str(temp_file),
            "doc_name": doc_name or file.filename,
            "options": options_dict,
            "temp_dir": temp_dir  # 用于后续清理
        }

        task_id = task_manager.create_task(params)

        return {
            "task_id": task_id,
            "status": "pending",
            "message": "索引任务已创建",
            "estimated_time": "预计处理时间 1-5 分钟"
        }

    except Exception as e:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"创建任务失败: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "TASK_CREATE_FAILED",
                    "message": str(e)
                }
            }
        )


@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态

    Args:
        task_id: 任务 ID

    Returns:
        任务状态和结果
    """
    task = task_manager.get_task(task_id)

    if not task:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": f"任务 {task_id} 不存在"
                }
            }
        )

    return task.to_dict()


@app.post("/retrieve")
async def retrieve(request: RetrieveRequest):
    """
    检索文档内容

    Args:
        request: 检索请求
            - doc_id: 文档 ID
            - query: 查询内容
            - options: 检索选项

    Returns:
        检索结果
            - page_ranges: 页码范围
            - title_pages: 标题页
            - material_pages: 证明材料页
            - answer: VLM 生成的答案
    """
    # 检查文档是否存在
    doc_info = task_manager.get_document(request.doc_id)
    if not doc_info:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "DOC_NOT_FOUND",
                    "message": f"文档 {request.doc_id} 不存在"
                }
            }
        )

    try:
        # 使用 VisionPageIndexClient 检索
        options = request.options or {}
        max_images = options.get("max_images", 0)  # 默认不调用VLM
        procurement_type = options.get("procurement_type")

        # 调用检索方法
        # 注意: retrieve_with_expansion 是同步方法，需要在线程中执行
        loop = asyncio.get_event_loop()

        def do_retrieve():
            return vision_client.retrieve_with_expansion(
                doc_id=request.doc_id,
                query=request.query,
                max_images=max_images,
                procurement_type=procurement_type
            )

        result = await loop.run_in_executor(None, do_retrieve)

        return {
            "success": True,
            "result": result
        }

    except Exception as e:
        logger.error(f"检索失败: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "RETRIEVE_FAILED",
                    "message": str(e)
                }
            }
        )


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    删除文档

    Args:
        doc_id: 文档 ID

    Returns:
        删除结果
    """
    success = task_manager.delete_document(doc_id)

    if not success:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "DOC_NOT_FOUND",
                    "message": f"文档 {doc_id} 不存在"
                }
            }
        )

    return {
        "success": True,
        "message": f"文档 {doc_id} 已删除"
    }


@app.get("/documents")
async def list_documents():
    """
    列出所有文档

    Returns:
        文档列表
    """
    documents = task_manager.list_documents()
    return {
        "success": True,
        "documents": documents,
        "count": len(documents)
    }


@app.get("/supported_types")
async def get_supported_types():
    """
    获取支持的评分项类型

    Returns:
        评分项类型列表
    """
    if procurement_kb:
        types = procurement_kb.get_all_requirement_types()
        return {
            "success": True,
            "types": types
        }
    return {
        "success": True,
        "types": []
    }


# ============== 主入口 ==============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=CONFIG["server"]["host"],
        port=CONFIG["server"]["port"]
    )