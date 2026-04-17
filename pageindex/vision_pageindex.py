"""
Vision PageIndex - 扫描件PDF智能检索模块

支持使用 VLM（视觉语言模型）处理扫描件PDF，结合 Agentic Retrieval 实现精确页码定位。

核心功能：
- 多轮扩展检索：标题页 + 证明材料页自动合并
- 采购评分项知识库：评分项类型与证明材料标准映射
- Agent智能检索：OpenAI Agents SDK 多工具协作

支持的模型：
- qwen-plus: 阿里云通义千问文本模型
- qwen-vl-plus: 阿里云通义千问视觉模型

使用流程：
1. PDF转图片 (extract_pdf_page_images)
2. VLM生成页面摘要 (generate_page_summaries_with_vlm)
3. 构建树索引 (VisionPageIndexClient)
4. 多轮扩展检索 (retrieve_with_expansion) - 推荐
5. Agent检索定位页码 (create_vision_agent) - 可选
6. VLM生成答案 (answer_with_vlm)

依赖：
- litellm: 统一LLM调用
- pymupdf/fitz: PDF转图片
- openai-agents: Agent框架（可选）
"""

import os
import json
import base64
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging

import litellm
import fitz  # PyMuPDF

# 兼容导入
try:
    from .utils import (
        llm_completion, llm_acompletion, extract_json,
        write_node_id, structure_to_list, remove_fields,
        ConfigLoader, print_tree
    )
    from .client import PageIndexClient
    from .procurement_knowledge import ProcurementKnowledgeBase, expand_page_range
except ImportError:
    from utils import (
        llm_completion, llm_acompletion, extract_json,
        write_node_id, structure_to_list, remove_fields,
        ConfigLoader, print_tree
    )
    from client import PageIndexClient
    from procurement_knowledge import ProcurementKnowledgeBase, expand_page_range

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== 配置 ==============

# LiteLLM 模型名称映射
MODEL_MAPPING = {
    "qwen-plus": "openai/qwen-plus",      # 通过 LiteLLM 调用阿里云
    "qwen-vl-plus": "openai/qwen-vl-plus",  # 视觉模型
}

# 默认配置
DEFAULT_CONFIG = {
    "text_model": "qwen-plus",
    "vision_model": "qwen-vl-plus",
    "image_zoom": 2.0,  # PDF转图片放大倍数
    "max_images_per_query": 5,  # 单次查询最大图片数
    "summary_max_length": 200,  # 摘要最大长度
}


# ============== PDF图片提取 ==============

def extract_pdf_page_images(
    pdf_path: str,
    output_dir: str = "pdf_images",
    zoom: float = 2.0,
    image_format: str = "jpeg"
) -> Dict[int, str]:
    """
    将PDF每页转换为图片

    Args:
        pdf_path: PDF文件路径
        output_dir: 图片输出目录
        zoom: 放大倍数（提高图片质量）
        image_format: 图片格式（jpeg/png）

    Returns:
        页码到图片路径的映射 {页码: 图片路径}

    Example:
        >>> page_images = extract_pdf_page_images("扫描件.pdf", "output_images")
        >>> print(page_images[1])  # 第1页图片路径
    """
    os.makedirs(output_dir, exist_ok=True)

    pdf_document = fitz.open(pdf_path)
    page_images = {}
    total_pages = len(pdf_document)

    logger.info(f"开始处理PDF: {pdf_path}, 共 {total_pages} 页")

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)

        # 设置放大倍数提高图片质量
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # 转换为指定格式
        img_data = pix.tobytes(image_format)

        # 保存图片
        image_path = os.path.join(
            output_dir,
            f"page_{page_number + 1}.{image_format}"
        )
        with open(image_path, "wb") as f:
            f.write(img_data)

        page_images[page_number + 1] = image_path
        logger.debug(f"已保存第 {page_number + 1} 页图片: {image_path}")

    pdf_document.close()
    logger.info(f"PDF图片提取完成，共 {len(page_images)} 页")

    return page_images


def get_page_images_for_range(
    page_images: Dict[int, str],
    pages: str
) -> List[str]:
    """
    根据页码范围获取图片路径

    Args:
        page_images: 页码到图片路径的映射
        pages: 页码字符串，如 "5-7", "3,8", "12"

    Returns:
        图片路径列表
    """
    # 解析页码
    page_nums = []
    for part in pages.split(','):
        part = part.strip()
        if '-' in part:
            start, end = int(part.split('-')[0]), int(part.split('-')[1])
            page_nums.extend(range(start, end + 1))
        else:
            page_nums.append(int(part))

    # 获取图片路径
    return [
        page_images[p]
        for p in sorted(set(page_nums))
        if p in page_images
    ]


# ============== VLM调用 ==============

def encode_image_to_base64(image_path: str) -> str:
    """
    将图片编码为base64字符串
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


async def call_vlm_async(
    prompt: str,
    image_paths: List[str] = None,
    model: str = "qwen-vl-plus"
) -> str:
    """
    异步调用VLM处理图片

    Args:
        prompt: 提示文本
        image_paths: 图片路径列表
        model: VLM模型名称

    Returns:
        模型响应文本

    Note:
        通过 LiteLLM 调用，需配置阿里云 API Key：
        os.environ["OPENAI_API_KEY"] = "your-dashscope-api-key"
        os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    """
    # 构建消息内容
    content = [{"type": "text", "text": prompt}]

    if image_paths:
        for image_path in image_paths:
            if os.path.exists(image_path):
                image_base64 = encode_image_to_base64(image_path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                })

    # 调用 LiteLLM
    model_name = MODEL_MAPPING.get(model, model)

    try:
        response = await litellm.acompletion(
            model=model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"VLM调用失败: {e}")
        raise


def call_vlm(
    prompt: str,
    image_paths: List[str] = None,
    model: str = "qwen-vl-plus"
) -> str:
    """
    同步调用VLM处理图片
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, call_vlm_async(prompt, image_paths, model)).result()
    except RuntimeError:
        return asyncio.run(call_vlm_async(prompt, image_paths, model))


# ============== 页面摘要生成 ==============

async def generate_page_summary_with_vlm(
    image_path: str,
    model: str = "qwen-vl-plus",
    max_length: int = 200
) -> str:
    """
    使用VLM为单页图片生成摘要

    Args:
        image_path: 页面图片路径
        model: VLM模型名称
        max_length: 摘要最大长度

    Returns:
        页面摘要文本
    """
    prompt = f"""请为这张文档页面生成简洁摘要，要求：
1. 概括页面主要内容（不超过{max_length}字）
2. 列出关键信息点（如标题、表格、重要数据）
3. 如有特殊元素（图表、签名、印章等）请标注

直接返回摘要内容，不要添加额外说明。"""

    summary = await call_vlm_async(prompt, [image_path], model)
    return summary.strip()


async def generate_page_summaries_batch(
    page_images: Dict[int, str],
    model: str = "qwen-vl-plus",
    max_length: int = 200,
    batch_size: int = 5
) -> Dict[int, str]:
    """
    批量生成页面摘要（并发处理）

    Args:
        page_images: 页码到图片路径的映射
        model: VLM模型名称
        max_length: 摘要最大长度
        batch_size: 并发批次大小

    Returns:
        页码到摘要的映射
    """
    summaries = {}
    pages = list(page_images.keys())

    logger.info(f"开始生成页面摘要，共 {len(pages)} 页")

    # 分批处理
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i + batch_size]
        tasks = [
            generate_page_summary_with_vlm(page_images[p], model, max_length)
            for p in batch
        ]

        batch_summaries = await asyncio.gather(*tasks)

        for p, summary in zip(batch, batch_summaries):
            summaries[p] = summary
            logger.info(f"第 {p} 页摘要已生成")

    logger.info(f"页面摘要生成完成，共 {len(summaries)} 页")
    return summaries


# ============== Vision增强客户端 ==============

class VisionPageIndexClient(PageIndexClient):
    """
    支持扫描件PDF的增强PageIndex客户端

    继承 PageIndexClient，添加：
    - 页面图片存储
    - VLM摘要生成
    - 图片检索支持

    Example:
        >>> client = VisionPageIndexClient(
        ...     text_model="qwen-plus",
        ...     vision_model="qwen-vl-plus"
        ... )
        >>> doc_id = client.index_scanned_pdf("扫描件.pdf")
        >>> result = client.retrieve_with_vlm(doc_id, "查找技术方案")
    """

    def __init__(
        self,
        text_model: str = "qwen-plus",
        vision_model: str = "qwen-vl-plus",
        api_key: str = None,
        base_url: str = None,
        workspace: str = None,
        **kwargs
    ):
        """
        初始化客户端

        Args:
            text_model: 文本模型名称
            vision_model: 视觉模型名称
            api_key: 阿里云 DashScope API Key
            base_url: API基础URL
            workspace: 工作空间目录
        """
        # 配置阿里云 API
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
        elif not os.getenv("OPENAI_BASE_URL"):
            # 默认阿里云 DashScope URL
            os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        # 设置模型
        self.text_model = MODEL_MAPPING.get(text_model, text_model)
        self.vision_model = MODEL_MAPPING.get(vision_model, vision_model)

        # 调用父类初始化（传递 workspace 参数）
        overrides = {"model": self.text_model, "retrieve_model": self.text_model}
        if workspace:
            kwargs["workspace"] = workspace
        super().__init__(**kwargs)

        # 更新配置
        opt = ConfigLoader().load(overrides)
        self.model = opt.model
        self.retrieve_model = opt.retrieve_model

        # 存储页面图片和摘要
        self.page_images: Dict[str, Dict[int, str]] = {}  # doc_id -> {页码: 图片路径}
        self.page_summaries: Dict[str, Dict[int, str]] = {}  # doc_id -> {页码: 摘要}

        # 加载已有的 vision 数据
        if self.workspace:
            self._load_vision_data()

    def _load_vision_data(self):
        """从 workspace 加载 page_images 和 page_summaries"""
        for doc_id, doc in self.documents.items():
            if doc.get('type') == 'scanned_pdf':
                # 尝试加载 vision 数据文件
                vision_path = self.workspace / f"{doc_id}_vision.json"
                if vision_path.exists():
                    try:
                        with open(vision_path, 'r', encoding='utf-8') as f:
                            vision_data = json.load(f)
                        self.page_images[doc_id] = vision_data.get('page_images', {})
                        # 转换页码为整数
                        self.page_images[doc_id] = {
                            int(k): v for k, v in self.page_images[doc_id].items()
                        }
                        self.page_summaries[doc_id] = vision_data.get('page_summaries', {})
                        self.page_summaries[doc_id] = {
                            int(k): v for k, v in self.page_summaries[doc_id].items()
                        }
                        logger.info(f"已加载 vision 数据: doc_id={doc_id}, 页数={len(self.page_images[doc_id])}")
                    except Exception as e:
                        logger.warning(f"加载 vision 数据失败: {e}")

    def _save_doc(self, doc_id: str):
        """保存文档索引（包括 vision 数据）"""
        # 先调用父类方法保存基本文档信息
        super()._save_doc(doc_id)

        # 保存 vision 数据
        doc = self.documents.get(doc_id)
        if doc and doc.get('type') == 'scanned_pdf':
            vision_path = self.workspace / f"{doc_id}_vision.json"
            vision_data = {
                'page_images': self.page_images.get(doc_id, {}),
                'page_summaries': self.page_summaries.get(doc_id, {})
            }
            with open(vision_path, 'w', encoding='utf-8') as f:
                json.dump(vision_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 vision 数据: {vision_path}")

    def find_doc_by_path(self, pdf_path: str) -> str | None:
        """
        根据 PDF 路径查找已有索引

        Args:
            pdf_path: PDF 文件绝对路径

        Returns:
            已有文档ID，如果不存在返回 None
        """
        pdf_path = os.path.abspath(pdf_path)
        for doc_id, doc in self.documents.items():
            if doc.get('type') == 'scanned_pdf' and doc.get('path') == pdf_path:
                # 检查是否已加载 vision 数据
                if doc_id in self.page_images and doc_id in self.page_summaries:
                    return doc_id
        return None

    def get_or_create_index(
        self,
        pdf_path: str,
        output_dir: str = None,
        force_reindex: bool = False
    ) -> str:
        """
        获取或创建索引（支持复用已有索引）

        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
            force_reindex: 是否强制重新索引

        Returns:
            文档ID
        """
        pdf_path = os.path.abspath(pdf_path)

        # 检查已有索引
        if not force_reindex:
            existing_doc_id = self.find_doc_by_path(pdf_path)
            if existing_doc_id:
                logger.info(f"使用已有索引: doc_id={existing_doc_id}")
                return existing_doc_id

        # 创建新索引
        return self.index_scanned_pdf(pdf_path, output_dir)

    def index_scanned_pdf(
        self,
        pdf_path: str,
        output_dir: str = None,
        generate_summaries: bool = True
    ) -> str:
        """
        索引扫描件PDF

        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录（默认为PDF同目录下的images文件夹）
            generate_summaries: 是否生成VLM摘要

        Returns:
            文档ID
        """
        pdf_path = os.path.abspath(pdf_path)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        # 设置输出目录
        if output_dir is None:
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_dir = os.path.join(os.path.dirname(pdf_path), f"{pdf_name}_images")

        # 提取PDF图片
        logger.info(f"提取PDF图片到: {output_dir}")
        page_images = extract_pdf_page_images(pdf_path, output_dir)

        # 生成VLM摘要（异步）
        if generate_summaries:
            logger.info("开始生成VLM页面摘要...")
            try:
                asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    page_summaries = pool.submit(
                        asyncio.run,
                        generate_page_summaries_batch(page_images, self.vision_model)
                    ).result()
            except RuntimeError:
                page_summaries = asyncio.run(
                    generate_page_summaries_batch(page_images, self.vision_model)
                )
        else:
            page_summaries = {}

        # 构建基于摘要的树结构
        logger.info("构建文档树结构...")
        structure = self._build_structure_from_summaries(page_summaries)

        # 生成文档ID
        import uuid
        doc_id = str(uuid.uuid4())

        # 存储文档信息
        pdf_reader = None
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(pdf_path)
            page_count = len(pdf_reader.pages)
        except:
            page_count = len(page_images)

        self.documents[doc_id] = {
            'id': doc_id,
            'type': 'scanned_pdf',  # 标记为扫描件
            'path': pdf_path,
            'doc_name': os.path.basename(pdf_path),
            'doc_description': self._generate_doc_description(page_summaries),
            'page_count': page_count,
            'structure': structure,
            'pages': [{'page': p, 'content': page_summaries.get(p, '')} for p in page_images.keys()],
        }

        # 存储图片和摘要映射
        self.page_images[doc_id] = page_images
        self.page_summaries[doc_id] = page_summaries

        logger.info(f"扫描件PDF索引完成，doc_id: {doc_id}")

        if self.workspace:
            self._save_doc(doc_id)

        return doc_id

    def _build_structure_from_summaries(
        self,
        page_summaries: Dict[int, str]
    ) -> List[Dict]:
        """
        基于页面摘要构建树结构

        Args:
            page_summaries: 页码到摘要的映射

        Returns:
            树结构列表
        """
        # 按页码排序
        sorted_pages = sorted(page_summaries.keys())

        if not sorted_pages:
            return []

        # 构建基础结构
        structure = []

        # 尝试使用LLM识别章节结构
        # 使用完整摘要，不截断，确保关键信息不丢失
        summaries_text = "\n".join([
            f"第{p}页: {s}"
            for p, s in page_summaries.items()
        ])

        prompt = f"""你是一个文档结构分析专家。
请根据以下页面摘要，识别文档的章节结构。

页面摘要：
{summaries_text}

请返回JSON格式的章节结构：
```json
[
  {{
    "title": "章节标题",
    "start_index": 开始页码,
    "end_index": 结束页码,
    "summary": "章节摘要",
    "nodes": [子章节列表]
  }}
]
```

注意：
1. 合理划分章节边界
2. 保持层级结构清晰
3. 为每个章节生成简洁摘要
"""

        try:
            response = llm_completion(self.text_model, prompt)
            structure = extract_json(response)

            if not structure:
                # 如果解析失败，构建简单的页码结构
                structure = [{
                    "title": "全部内容",
                    "start_index": sorted_pages[0],
                    "end_index": sorted_pages[-1],
                    "summary": "扫描件PDF文档",
                    "nodes": [
                        {
                            "title": f"第{p}页",
                            "start_index": p,
                            "end_index": p,
                            "summary": page_summaries[p]  # 不截断
                        }
                        for p in sorted_pages
                    ]
                }]

            # 添加node_id
            write_node_id(structure)

        except Exception as e:
            logger.warning(f"结构生成失败，使用默认结构: {e}")
            structure = [{
                "title": "全部内容",
                "node_id": "0000",
                "start_index": sorted_pages[0],
                "end_index": sorted_pages[-1],
                "summary": "扫描件PDF文档",
                "nodes": [
                    {
                        "title": f"第{p}页",
                        "node_id": str(i).zfill(4),
                        "start_index": p,
                        "end_index": p,
                        "summary": page_summaries.get(p, '')  # 不截断
                    }
                    for i, p in enumerate(sorted_pages, 1)
                ]
            }]

        return structure

    def _generate_doc_description(
        self,
        page_summaries: Dict[int, str]
    ) -> str:
        """
        生成文档描述
        """
        if not page_summaries:
            return "扫描件PDF文档"

        # 使用前几页摘要生成描述
        first_pages = sorted(page_summaries.keys())[:3]
        first_summaries = [page_summaries[p][:50] for p in first_pages]

        prompt = f"""根据以下页面内容摘要，生成一句文档描述：

{chr(10).join(first_summaries)}

直接返回描述，不超过50字。"""

        try:
            return llm_completion(self.text_model, prompt).strip()
        except:
            return "扫描件PDF文档"

    def _locate_keyword_pages(
        self,
        query: str,
        page_summaries: Dict[int, str],
        check_material_pages: bool = True,
        max_material_pages: int = 3
    ) -> Dict[str, Any]:
        """
        两阶段关键词定位策略

        阶段1: 定位包含关键词的标题页
        阶段2: 扫描后续证明材料页

        Args:
            query: 查询关键词
            page_summaries: 页码到摘要的映射
            check_material_pages: 是否检查证明材料页
            max_material_pages: 每个标题页最多检查后续几页

        Returns:
            {
                'title_pages': [87],  # 包含关键词的页面
                'material_pages': [88, 89],  # 证明材料页
                'full_range': '87-89',  # 合并后的完整范围
                'reason': '定位理由'
            }
        """
        if not page_summaries:
            return {'title_pages': [], 'material_pages': [], 'full_range': '', 'reason': '无摘要数据'}

        # 阶段1: 在摘要中搜索关键词（不区分大小写）
        title_pages = []
        query_lower = query.lower()

        for page_num, summary in page_summaries.items():
            if query_lower in summary.lower():
                title_pages.append(page_num)
                logger.info(f"在摘要中发现关键词 '{query}' 于第 {page_num} 页")

        if not title_pages:
            logger.warning(f"未在摘要中找到关键词 '{query}'")
            return {'title_pages': [], 'material_pages': [], 'full_range': '', 'reason': '未找到关键词'}

        # 阶段2: 对每个标题页，检查后续页面是否为证明材料
        material_pages = []

        if check_material_pages:
            for title_page in title_pages:
                # 检查后续 max_material_pages 页是否为证明材料
                max_page = max(page_summaries.keys())
                for next_page in range(title_page + 1, min(title_page + max_material_pages + 1, max_page + 1)):
                    if next_page in page_summaries:
                        # 使用LLM判断是否语义属于该评分项
                        is_material = self._check_material_belonging(
                            page_summaries[next_page], query
                        )
                        if is_material:
                            material_pages.append(next_page)
                            logger.info(f"第 {next_page} 页被识别为 '{query}' 的证明材料页")

        # 合并所有页码
        all_pages = sorted(set(title_pages + material_pages))

        if all_pages:
            full_range = f"{all_pages[0]}-{all_pages[-1]}"
        else:
            full_range = ""

        # 生成定位理由
        reason = f"标题页: {title_pages}, 证明材料页: {material_pages}"

        return {
            'title_pages': title_pages,
            'material_pages': material_pages,
            'full_range': full_range,
            'reason': reason
        }

    def _check_material_belonging(
        self,
        page_summary: str,
        keyword: str
    ) -> bool:
        """
        使用LLM判断页面是否语义属于该评分项

        判断规则：
        - 人员配备：人员名单、证书、操作手合格证、培训证明
        - 类似业绩：中标通知书、合同、业绩证明
        - 设备能力：设备清单、设备发票、设备参数
        - 技术方案：技术设计、方案说明

        Args:
            page_summary: 页面摘要
            keyword: 关键词

        Returns:
            是否属于该评分项的证明材料
        """
        # 定义关键词与证明材料的对应关系
        material_patterns = {
            '人员配备': ['人员名单', '证书', '合格证', '培训证明', '操作手', '身份证', '资质', '简历'],
            '类似业绩': ['中标通知书', '合同', '业绩证明', '业绩表', '项目案例', '服务证明'],
            '设备能力': ['设备清单', '设备发票', '设备参数', '设备表', '飞机', '无人机', '机械'],
            '技术方案': ['技术设计', '方案说明', '实施方案', '技术措施', '工艺流程'],
            '售后服务': ['售后承诺', '服务方案', '保修', '维护', '服务响应'],
        }

        # 查找对应的关键词模式
        patterns = []
        for key, values in material_patterns.items():
            if key.lower() in keyword.lower():
                patterns = values
                break

        # 如果没有匹配的预设模式，使用通用判断
        if not patterns:
            patterns = ['证书', '合同', '清单', '证明', '承诺', '方案']

        # 先做简单的关键词匹配
        summary_lower = page_summary.lower()
        for pattern in patterns:
            if pattern.lower() in summary_lower:
                logger.info(f"摘要中包含证明材料关键词 '{pattern}'")
                return True

        # 如果简单匹配失败，使用LLM进行更精确的语义判断
        prompt = '判断这个页面摘要是否属于"' + keyword + '"评分项的证明材料。\n\n页面摘要：' + page_summary + '\n\n判断规则：\n1. 如果摘要包含证书、合同、清单等证明材料关键词\n2. 如果摘要内容明显与"' + keyword + '"相关（如人员证书、设备清单）\n3. 即使不包含"' + keyword + '"字样，如果是相关证明材料也应返回true\n\n返回 JSON：{"belongs_to": true或false, "reason": "判断理由"}'

        try:
            response = llm_completion(self.text_model, prompt)
            result = extract_json(response)
            return result.get('belongs_to', False)
        except Exception as e:
            logger.warning(f"语义判断失败: {e}")
            return False

    def get_page_images(
        self,
        doc_id: str,
        pages: str
    ) -> List[str]:
        """
        获取指定页面的图片路径

        Args:
            doc_id: 文档ID
            pages: 页码字符串，如 "5-7", "3,8", "12"

        Returns:
            图片路径列表
        """
        doc_info = self.documents.get(doc_id)
        if not doc_info:
            raise ValueError(f"文档不存在: {doc_id}")

        page_images = self.page_images.get(doc_id, {})
        if not page_images:
            raise ValueError(f"文档无图片数据: {doc_id}")

        return get_page_images_for_range(page_images, pages)

    def retrieve_with_expansion(
        self,
        doc_id: str,
        query: str,
        max_images: int = 10,
        knowledge_base: ProcurementKnowledgeBase = None,
        procurement_type: str = None  # 新增：采购类型过滤
    ) -> Dict[str, Any]:
        """
        多轮扩展检索：标题页 + 证明材料页自动合并

        这是采购文件场景的最佳实践方案：
        1. 解析用户查询意图 → 识别评分项类型
        2. 定位标题页 → 在摘要中搜索关键词
        3. 扫描证明材料页 → 向后扩展检测相关证明材料
        4. 合并范围 → 输出完整页码范围

        Args:
            doc_id: 文档ID
            query: 用户查询（如"人员配备"、"类似业绩"）
            max_images: 最大图片数（用于VLM处理）
            knowledge_base: 自定义知识库（默认使用内置）
            procurement_type: 采购类型过滤（可选）
                             None = 不过滤（默认）
                             "货物类" = 仅检索货物类评分项
                             "服务类" = 仅检索服务类评分项

        Returns:
            {
                'query': 查询文本,
                'requirement_type': 评分项类型,
                'procurement_type': 采购类型,
                'page_ranges': 合并后的页码范围,
                'title_pages': 标题页列表,
                'material_pages': 证明材料页列表,
                'material_details': 证明材料详情,
                'image_paths': 图片路径,
                'answer': VLM答案,
                'confidence': 匹配置信度
            }
        """
        # 初始化知识库
        kb = knowledge_base or ProcurementKnowledgeBase()

        # 获取页面摘要
        page_summaries = self.page_summaries.get(doc_id, {})
        if not page_summaries:
            raise ValueError(f"文档无摘要数据: {doc_id}")

        max_page = max(page_summaries.keys())

        # 导入 ProcurementType 用于类型转换
        from .procurement_knowledge import ProcurementType

        # 转换 procurement_type 参数
        proc_type_enum = None
        if procurement_type:
            if procurement_type == "货物类":
                proc_type_enum = ProcurementType.GOODS
            elif procurement_type == "服务类":
                proc_type_enum = ProcurementType.SERVICES
            else:
                logger.warning(f"未知的采购类型: {procurement_type}, 将忽略类型过滤")

        # Step 1: 解析用户查询意图（支持类型过滤）
        intent = kb.parse_intent(query, procurement_type=proc_type_enum)
        requirement_type = intent.get('requirement_type')
        title_keywords = intent.get('title_keywords', [])
        material_types = intent.get('material_types', {})
        expansion_rule = intent.get('page_expansion_rule', {})
        confidence = intent.get('confidence', 0)

        logger.info(f"意图解析: requirement_type={requirement_type}, procurement_type={procurement_type}, confidence={confidence}")

        # Step 2: 定位标题页（优先精确匹配，排除汇总表）
        title_pages = []
        title_page_scores = {}  # 记录每个标题页的匹配分数

        # 获取排除词列表
        exclude_keywords = intent.get('exclude_keywords', [])

        for page, summary in page_summaries.items():
            # 检查是否包含排除词（如"偏离表"、"响应表"）
            is_excluded = False
            for ex_kw in exclude_keywords:
                if ex_kw in summary:
                    is_excluded = True
                    logger.info(f"排除页面: 第{page}页 (包含排除词: {ex_kw})")
                    break

            if is_excluded:
                continue

            # 检查摘要是否包含标题关键词
            match_count = 0
            exact_match = False  # 是否有与查询词完全匹配的关键词
            matched_keywords = []
            for kw in title_keywords:
                if kw in summary:
                    match_count += 1
                    matched_keywords.append(kw)
                    # 检查是否精确匹配查询词
                    if kw == query or query in kw:
                        exact_match = True

            if match_count > 0:
                title_pages.append(page)
                # 精确匹配得分更高
                title_page_scores[page] = match_count + (10 if exact_match else 0)
                logger.info(f"发现标题页: 第{page}页 (关键词: {matched_keywords}, 精确匹配: {exact_match})")

        if not title_pages:
            # 没有找到标题页，尝试用原始查询词搜索（仍需排除排除词）
            for page, summary in page_summaries.items():
                # 检查排除词
                is_excluded = False
                for ex_kw in exclude_keywords:
                    if ex_kw in summary:
                        is_excluded = True
                        break
                if is_excluded:
                    continue

                if query in summary:
                    title_pages.append(page)
                    title_page_scores[page] = 11  # 给予较高分数
                    logger.info(f"用查询词定位: 第{page}页")

        # 选择最相关的标题页进行扩展（匹配分数最高的）
        primary_title_page = max(title_page_scores, key=title_page_scores.get) if title_page_scores else None
        logger.info(f"主要标题页: {primary_title_page} (分数: {title_page_scores.get(primary_title_page)})")

        # Step 3: 扫描证明材料页（只对主要标题页进行扩展）
        material_pages = []
        material_details = []
        seen_material_pages = set()  # 去重

        # 获取所有证明材料关键词
        all_material_keywords = kb.get_material_keywords(requirement_type) if requirement_type != "unknown" else []

        # 获取扩展规则
        direction = expansion_rule.get('direction', 'forward')
        max_expansion = expansion_rule.get('max_pages', 5)

        # 只对主要标题页进行扩展扫描（避免误扩展到其他评分项）
        scan_targets = [primary_title_page] if primary_title_page else []

        for title_page in scan_targets:
            # 根据方向决定扫描范围
            if direction == 'forward':
                scan_start = title_page + 1
                scan_end = min(title_page + max_expansion + 1, max_page + 1)
            elif direction == 'backward':
                scan_start = max(1, title_page - max_expansion)
                scan_end = title_page
            elif direction == 'section':
                # 整个部分，扫描更广范围
                scan_start = title_page + 1
                scan_end = min(title_page + max_expansion + 1, max_page + 1)
            else:
                continue

            # 扫描后续页面
            for scan_page in range(scan_start, scan_end):
                if scan_page not in page_summaries or scan_page in seen_material_pages:
                    continue

                scan_summary = page_summaries[scan_page]

                # 检查是否为证明材料
                if requirement_type != "unknown":
                    mat_result = kb.check_page_is_material(scan_summary, requirement_type)
                    if mat_result['is_material']:
                        seen_material_pages.add(scan_page)
                        material_pages.append(scan_page)
                        material_details.append({
                            'page': scan_page,
                            'material_type': mat_result['material_type'],
                            'matched_keywords': mat_result['matched_keywords'],
                            'description': mat_result.get('description', ''),
                        })
                        logger.info(f"发现证明材料页: 第{scan_page}页 ({mat_result['material_type']})")
                else:
                    # 使用通用关键词检测
                    for kw in all_material_keywords:
                        if kw in scan_summary:
                            seen_material_pages.add(scan_page)
                            material_pages.append(scan_page)
                            logger.info(f"发现证明材料页: 第{scan_page}页 (关键词: {kw})")
                            break

        # Step 4: 合并范围（只合并主要标题页及其证明材料页）
        # 将主要标题页添加到证明材料页列表的开头（如果不在）
        relevant_pages = sorted(set([primary_title_page] + material_pages) if primary_title_page else material_pages)
        page_ranges = expand_page_range([primary_title_page] if primary_title_page else [], material_pages)

        # 输出日志
        logger.info(f"多轮扩展检索完成: 主要标题页={primary_title_page}, 证明材料页={material_pages}")
        logger.info(f"合并范围: {page_ranges}")

        # 获取图片路径
        image_paths = []
        if relevant_pages:
            combined_range = f"{relevant_pages[0]}-{relevant_pages[-1]}"
            image_paths = self.get_page_images(doc_id, combined_range)
            # 限制图片数量
            if len(image_paths) > max_images:
                image_paths = image_paths[:max_images]
                logger.warning(f"图片数量超过限制({max_images})，已截断")

        # 使用VLM生成答案
        vlm_prompt = f"""请根据以下文档图片回答问题：

问题：{query}

已识别：
- 评分项类型：{requirement_type}
- 标题页：{title_pages}
- 证明材料页：{material_pages}

请：
1. 综合标题页和证明材料页内容，完整回答问题
2. 标注答案来源的页码
3. 说明证明材料如何支撑评分项要求

答案格式：
【答案】xxx
【来源页码】xxx
【证明材料说明】xxx
"""
        answer = ""
        if image_paths:
            try:
                answer = call_vlm(vlm_prompt, image_paths, self.vision_model)
            except Exception as e:
                logger.warning(f"VLM调用失败: {e}")
                answer = f"VLM处理失败，请查看图片: {image_paths}"

        return {
            'query': query,
            'requirement_type': requirement_type,
            'procurement_type': procurement_type,  # 新增：采购类型
            'primary_title_page': primary_title_page,  # 主要标题页（精确匹配）
            'title_pages': title_pages,  # 所有匹配的标题页
            'material_pages': material_pages,  # 证明材料页
            'relevant_pages': relevant_pages,  # 相关页码（主要标题页 + 证明材料页）
            'page_ranges': page_ranges,  # 合并范围
            'material_details': material_details,
            'image_paths': image_paths,
            'answer': answer,
            'confidence': confidence,
            'intent': intent,
            'location_method': 'expansion_based',
        }

    def retrieve_with_vlm(
        self,
        doc_id: str,
        query: str,
        max_images: int = 5,
        use_keyword_location: bool = True
    ) -> Dict[str, Any]:
        """
        使用VLM进行检索

        Args:
            doc_id: 文档ID
            query: 查询文本
            max_images: 最大图片数
            use_keyword_location: 是否优先使用关键词定位策略

        Returns:
            检索结果，包含页码和VLM生成的答案
        """
        # 获取页面摘要
        page_summaries = self.page_summaries.get(doc_id, {})

        # 优先使用关键词定位策略（两阶段定位）
        if use_keyword_location and page_summaries:
            location_result = self._locate_keyword_pages(query, page_summaries)

            if location_result['full_range']:
                logger.info(f"关键词定位成功: {location_result}")
                page_ranges = [location_result['full_range']]
                # 直接跳转到VLM处理
                image_paths = self.get_page_images(doc_id, page_ranges[0])

                # 限制图片数量
                if len(image_paths) > max_images:
                    image_paths = image_paths[:max_images]
                    logger.warning(f"图片数量超过限制，只取前{max_images}张")

                # 使用VLM生成答案
                vlm_prompt = f"""请根据以下文档图片回答问题：

问题：{query}

请：
1. 直接回答问题
2. 标注答案来源的页码
3. 如需更多信息，说明还需要哪些页面

答案格式：
【答案】xxx
【来源页码】xxx
【补充说明】xxx（如需要）
"""

                answer = call_vlm(vlm_prompt, image_paths, self.vision_model)

                return {
                    'query': query,
                    'page_ranges': page_ranges,
                    'title_pages': location_result.get('title_pages', []),
                    'material_pages': location_result.get('material_pages', []),
                    'thinking': location_result.get('reason', ''),
                    'reason': location_result.get('reason', ''),
                    'image_paths': image_paths,
                    'answer': answer,
                    'location_method': 'keyword_based'
                }

        # 回退到结构定位
        logger.info("关键词定位未成功，回退到结构定位")
        structure = self.documents.get(doc_id, {}).get('structure', [])
        structure_no_text = remove_fields(structure, fields=['text'])

        # 使用LLM在结构中定位相关页码
        prompt = f"""你是一个文档检索专家。
请根据以下文档结构和用户查询，定位相关页码范围。

文档结构：
{json.dumps(structure_no_text, ensure_ascii=False, indent=2)}

用户查询：{query}

请返回JSON格式：
```json
{
  "thinking": "推理过程",
  "page_ranges": ["5-7", "10-12"],
  "reason": "定位理由"
}
```

注意：页码范围要精确，每个范围不超过{max_images}页。
"""

        response = llm_completion(self.text_model, prompt)
        result = extract_json(response)

        if not result or 'page_ranges' not in result:
            # 默认返回首页
            result = {
                'thinking': '无法定位，返回首页',
                'page_ranges': ['1'],
                'reason': '默认范围'
            }

        # 获取所有页码的图片
        all_pages = []
        for range_str in result['page_ranges']:
            all_pages.append(range_str)

        # 合并页码范围
        merged_pages = ','.join(all_pages)

        # 获取图片
        image_paths = self.get_page_images(doc_id, merged_pages)

        # 限制图片数量
        if len(image_paths) > max_images:
            # 只取前max_images张
            image_paths = image_paths[:max_images]
            logger.warning(f"图片数量超过限制，只取前{max_images}张")

        # 使用VLM生成答案
        vlm_prompt = f"""请根据以下文档图片回答问题：

问题：{query}

请：
1. 直接回答问题
2. 标注答案来源的页码
3. 如需更多信息，说明还需要哪些页面

答案格式：
【答案】xxx
【来源页码】xxx
【补充说明】xxx（如需要）
"""

        answer = call_vlm(vlm_prompt, image_paths, self.vision_model)

        return {
            'query': query,
            'page_ranges': result.get('page_ranges', []),
            'thinking': result.get('thinking', ''),
            'reason': result.get('reason', ''),
            'image_paths': image_paths,
            'answer': answer,
            'location_method': 'structure_based'  # 标识使用了结构定位
        }


# ============== Agent工具函数 ==============

def create_vision_agent_tools(
    client: VisionPageIndexClient,
    doc_id: str
) -> Dict[str, Any]:
    """
    创建用于Agent的工具函数

    Args:
        client: VisionPageIndexClient实例
        doc_id: 文档ID

    Returns:
        工具函数字典

    Note:
        返回的工具函数可直接用于 openai-agents 的 @function_tool
    """

    def get_document() -> str:
        """获取文档元数据"""
        return client.get_document(doc_id)

    def get_document_structure() -> str:
        """获取文档树结构"""
        return client.get_document_structure(doc_id)

    def get_page_content(pages: str) -> str:
        """
        获取页面内容（扫描件返回摘要）

        Args:
            pages: 页码范围，如 "5-7", "3,8", "12"
        """
        doc_info = client.documents.get(doc_id)
        if doc_info and doc_info.get('type') == 'scanned_pdf':
            # 返回摘要而非原文
            summaries = client.page_summaries.get(doc_id, {})
            page_nums = []
            for part in pages.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = int(part.split('-')[0]), int(part.split('-')[1])
                    page_nums.extend(range(start, end + 1))
                else:
                    page_nums.append(int(part))

            content = [
                {'page': p, 'summary': summaries.get(p, '无摘要')}
                for p in sorted(set(page_nums))
                if p in summaries
            ]
            return json.dumps(content, ensure_ascii=False)
        return client.get_page_content(doc_id, pages)

    def get_page_images(pages: str) -> str:
        """
        获取页面图片路径（用于VLM处理）

        Args:
            pages: 页码范围，如 "5-7", "3,8", "12"
        """
        try:
            image_paths = client.get_page_images(doc_id, pages)
            return json.dumps({
                'type': 'images',
                'pages': pages,
                'image_paths': image_paths,
                'count': len(image_paths)
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def retrieve_with_expansion(query: str, max_images: int = 10) -> str:
        """
        多轮扩展检索：自动识别评分项并合并标题页+证明材料页

        这是采购文件场景的最佳检索方式，会：
        1. 解析用户查询意图，识别评分项类型
        2. 定位标题页（排除偏离表等汇总页面）
        3. 扫描证明材料页（如操作证、合同、发票等）
        4. 合并完整页码范围

        Args:
            query: 用户查询，如"人员配备"、"类似业绩"、"技术方案"
            max_images: 最大图片数量限制

        Returns:
            JSON格式的检索结果，包含：
            - requirement_type: 评分项类型
            - primary_title_page: 主要标题页
            - material_pages: 证明材料页列表
            - page_ranges: 合并后的页码范围
            - image_paths: 图片路径
        """
        try:
            result = client.retrieve_with_expansion(doc_id, query, max_images=max_images)
            # 简化输出，只返回关键信息
            output = {
                'requirement_type': result.get('requirement_type'),
                'primary_title_page': result.get('primary_title_page'),
                'title_pages': result.get('title_pages'),
                'material_pages': result.get('material_pages'),
                'page_ranges': result.get('page_ranges'),
                'material_details': [
                    {'page': d['page'], 'type': d['material_type']}
                    for d in result.get('material_details', [])
                ],
                'image_paths': result.get('image_paths', [])[:max_images],
                'confidence': result.get('confidence'),
            }
            return json.dumps(output, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def get_supported_requirement_types() -> str:
        """
        获取支持的采购评分项类型列表

        用于帮助用户了解可以查询的评分项类型
        """
        try:
            kb = ProcurementKnowledgeBase()
            types = kb.get_all_requirement_types()
            categories = {}
            for t in types:
                intent = kb.parse_intent(t)
                cat = intent.get('category', '其他')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(t)
            return json.dumps({
                'supported_types': types,
                'by_category': categories,
                'usage': '查询时使用这些关键词可获得最佳检索效果'
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)})

    return {
        'get_document': get_document,
        'get_document_structure': get_document_structure,
        'get_page_content': get_page_content,
        'get_page_images': get_page_images,
        'retrieve_with_expansion': retrieve_with_expansion,
        'get_supported_requirement_types': get_supported_requirement_types,
    }


# ============== Agent创建（可选，需安装openai-agents）=============

def create_chat_completions_model_provider(
    api_key: str = None,
    base_url: str = None
):
    """
    创建使用 Chat Completions API 的 ModelProvider

    用于兼容阿里云 DashScope 等 OpenAI-compatible API

    Args:
        api_key: API密钥，默认从环境变量获取
        base_url: API基础URL，默认从环境变量获取

    Returns:
        ModelProvider实例

    Note:
        需要安装: pip install openai-agents
    """
    try:
        from agents import ModelProvider
        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
        from openai import AsyncOpenAI
    except ImportError:
        raise ImportError("需要安装 openai-agents: pip install openai-agents")

    # 获取配置
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("需要设置 OPENAI_API_KEY 环境变量")

    # 创建 OpenAI 客户端
    openai_client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )

    class _ChatCompletionsModelProvider(ModelProvider):
        def __init__(self, client: AsyncOpenAI):
            self._client = client

        def get_model(self, model_name: str | None):
            return OpenAIChatCompletionsModel(model_name, self._client)

        async def aclose(self):
            await self._client.close()

    return _ChatCompletionsModelProvider(openai_client)


def create_vision_agent(
    client: VisionPageIndexClient,
    doc_id: str,
    agent_model: str = None
):
    """
    创建Vision检索Agent（使用openai-agents）

    Args:
        client: VisionPageIndexClient实例
        doc_id: 文档ID
        agent_model: Agent使用的模型

    Returns:
        Agent实例

    Note:
        需要安装: pip install openai-agents
    """
    try:
        from agents import Agent, function_tool
    except ImportError:
        raise ImportError("需要安装 openai-agents: pip install openai-agents")

    # 获取工具函数
    tools_dict = create_vision_agent_tools(client, doc_id)

    # 包装为function_tool
    @function_tool
    def get_document() -> str:
        """获取文档元数据：状态、页数、名称、描述"""
        return tools_dict['get_document']()

    @function_tool
    def get_document_structure() -> str:
        """获取文档树结构索引，用于定位相关章节"""
        return tools_dict['get_document_structure']()

    @function_tool
    def get_page_content(pages: str) -> str:
        """获取页面内容摘要，参数格式: '5-7', '3,8', '12'"""
        return tools_dict['get_page_content'](pages)

    @function_tool
    def get_page_images(pages: str) -> str:
        """获取页面图片路径，用于VLM视觉处理，参数格式: '5-7', '3,8', '12'"""
        return tools_dict['get_page_images'](pages)

    @function_tool
    def retrieve_with_expansion(query: str, max_images: int = 10) -> str:
        """多轮扩展检索：自动识别评分项类型并合并标题页+证明材料页。推荐用于采购文件检索，如查询'人员配备'会自动定位标题页并扫描后续的操作证、培训证明等证明材料页。参数: query-评分项关键词如'人员配备'、'类似业绩'，max_images-最大图片数"""
        return tools_dict['retrieve_with_expansion'](query, max_images)

    @function_tool
    def get_supported_requirement_types() -> str:
        """获取支持的采购评分项类型列表，帮助用户了解可以查询的评分项"""
        return tools_dict['get_supported_requirement_types']()

    # 创建Agent
    # 确保模型名称不带 "openai/" 前缀（openai-agents SDK 会自动添加）
    agent_model = agent_model or client.retrieve_model
    if agent_model and agent_model.startswith("openai/"):
        agent_model = agent_model.replace("openai/", "", 1)
    if agent_model and agent_model.startswith("litellm/"):
        agent_model = agent_model.replace("litellm/", "", 1)

    agent = Agent(
        name="VisionPageIndex",
        instructions="""
你是采购文件智能检索助手，专门处理扫描件PDF响应文件的页码定位。

## 核心能力
采购文件采用"标题页 + 证明材料页"结构，证明材料页（证书、合同、发票等）不含评分项关键词，需要智能扩展检索。

## 检索策略（推荐）

### 方式一：多轮扩展检索（推荐用于采购评分项）
直接调用 `retrieve_with_expansion(query)` 进行智能检索：
- 自动识别评分项类型（人员配备、类似业绩、设备能力等）
- 定位标题页（排除偏离表等汇总页面）
- 扫描证明材料页（操作证、合同、发票等）
- 合并完整页码范围

适用场景：
- 查询评分项：人员配备、类似业绩、设备能力、企业资质等
- 需要完整证明材料范围

### 方式二：手动逐步检索（用于非评分项查询）
1. 调用 get_document() 获取文档信息
2. 调用 get_document_structure() 查看文档结构
3. 调用 get_page_content(pages) 获取页面摘要判断相关性
4. 调用 get_page_images(pages) 获取图片路径

## 工具说明
- `retrieve_with_expansion`: 多轮扩展检索，自动合并标题页+证明材料页
- `get_supported_requirement_types`: 查看支持的评分项类型
- `get_page_content`: 获取页面摘要（用于检查特定页面）
- `get_page_images`: 获取图片路径（用于VLM处理）

## 输出格式
【评分项类型】xxx
【定位页码】xxx（已合并标题页和证明材料页）
【标题页】xxx
【证明材料页】xxx（操作证、合同、发票等）
【图片路径】xxx
【建议】可使用VLM处理这些图片获取完整答案

## 重要提示
- 采购文件检索优先使用 retrieve_with_expansion
- 证明材料页可能不含关键词，但语义上属于评分项
- 偏离表、响应表等汇总页面不是证明材料，应排除
""",
        tools=[
            retrieve_with_expansion,  # 优先工具
            get_supported_requirement_types,
            get_document,
            get_document_structure,
            get_page_content,
            get_page_images,
        ],
        model=agent_model
    )

    return agent


# ============== 便捷函数 ==============

async def answer_with_vlm(
    query: str,
    image_paths: List[str],
    model: str = "qwen-vl-plus"
) -> str:
    """
    使用VLM处理图片生成答案

    Args:
        query: 用户查询
        image_paths: 图片路径列表
        model: VLM模型名称

    Returns:
        VLM生成的答案
    """
    prompt = f"""请根据以下文档图片回答问题：

问题：{query}

要求：
1. 直接、准确回答问题
2. 标注答案来源的具体页码
3. 如有表格、图表数据，请准确提取
4. 如需更多信息，说明需要查看其他页面

答案格式：
【答案】xxx
【来源页码】第X页
【关键信息】xxx（如有表格数据等）
"""

    return await call_vlm_async(prompt, image_paths, model)


def process_scanned_pdf_query(
    pdf_path: str,
    query: str,
    api_key: str = None,
    text_model: str = "qwen-plus",
    vision_model: str = "qwen-vl-plus"
) -> Dict[str, Any]:
    """
    一站式处理扫描件PDF查询

    Args:
        pdf_path: PDF文件路径
        query: 查询问题
        api_key: 阿里云API Key
        text_model: 文本模型
        vision_model: 视觉模型

    Returns:
        完整检索结果

    Example:
        >>> result = process_scanned_pdf_query(
        ...     "响应文件.pdf",
        ...     "查找技术方案设计说明",
        ...     api_key="your-dashscope-key"
        ... )
        >>> print(result['answer'])
    """
    # 初始化客户端
    client = VisionPageIndexClient(
        text_model=text_model,
        vision_model=vision_model,
        api_key=api_key
    )

    # 索引扫描件
    doc_id = client.index_scanned_pdf(pdf_path)

    # 检索
    result = client.retrieve_with_vlm(doc_id, query)

    return result


# ============== 批量检索（采购文件场景）=============

async def batch_retrieve_for_requirements(
    client: VisionPageIndexClient,
    doc_id: str,
    requirements: List[str],
    max_images_per_req: int = 5
) -> List[Dict[str, Any]]:
    """
    批量检索采购要求

    Args:
        client: VisionPageIndexClient实例
        doc_id: 文档ID
        requirements: 采购要求列表
        max_images_per_req: 每个要求最大图片数

    Returns:
        检索结果列表

    Example:
        >>> requirements = [
        ...     "技术方案设计说明",
        ...     "项目实施计划",
        ...     "人员配置方案"
        ... ]
        >>> results = await batch_retrieve_for_requirements(client, doc_id, requirements)
    """
    results = []

    for req in requirements:
        logger.info(f"检索要求: {req}")

        # 定位页码
        result = client.retrieve_with_vlm(doc_id, req, max_images_per_req)

        # 使用VLM验证内容
        if result.get('image_paths'):
            # 构建验证prompt
            verify_prompt = f"""请验证响应文件是否满足采购要求：

采购要求：{req}

请：
1. 判断是否满足要求（满足/部分满足/不满足）
2. 如满足，说明具体内容位置
3. 如不满足或部分满足，说明缺失内容

返回JSON格式：
```json
{
  "status": "满足/部分满足/不满足",
  "satisfied_content": "已满足的内容",
  "missing_content": "缺失的内容",
  "page_location": "内容所在页码"
}
```
"""

            verify_result = await call_vlm_async(
                verify_prompt,
                result['image_paths'],
                client.vision_model
            )

            result['verification'] = extract_json(verify_result)

        result['requirement'] = req
        results.append(result)

    return results


def generate_retrieval_report(
    results: List[Dict[str, Any]]
) -> str:
    """
    生成检索报告

    Args:
        results: 批量检索结果

    Returns:
        格式化的报告文本
    """
    report = "# 响应文件检索报告\n\n"

    for i, result in enumerate(results, 1):
        req = result.get('requirement', '未知要求')
        status = result.get('verification', {}).get('status', '待验证')

        report += f"## {i}. {req}\n\n"
        report += f"**状态**: {status}\n\n"

        if result.get('page_ranges'):
            report += f"**定位页码**: {', '.join(result['page_ranges'])}\n\n"

        if result.get('verification'):
            ver = result['verification']
            if ver.get('satisfied_content'):
                report += f"**已满足内容**: {ver['satisfied_content']}\n\n"
            if ver.get('missing_content'):
                report += f"**缺失内容**: {ver['missing_content']}\n\n"
            if ver.get('page_location'):
                report += f"**具体位置**: {ver['page_location']}\n\n"

        if result.get('answer'):
            report += f"**详细答案**: {result['answer'][:200]}...\n\n"

        report += "---\n\n"

    return report