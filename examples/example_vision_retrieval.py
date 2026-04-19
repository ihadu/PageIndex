"""
扫描件PDF Agentic Retrieval 示例

演示如何使用 Vision PageIndex 处理扫描件PDF并进行智能检索。

模型支持：
- qwen3.5-flash: 阿里云通义千问3文本模型（用于推理，性价比高）
- qwen3-vl-flash: 阿里云通义千问3视觉模型（用于处理图片，性价比高）

前置条件：
1. 安装依赖: pip install litellm pymupdf openai-agents
2. 配置阿里云API Key:
   - 设置环境变量 DASHSCOPE_API_KEY
   - 或在代码中传入 api_key 参数

使用方式：
    python example_vision_retrieval.py --pdf 响应文件.pdf --query "查找技术方案"
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============== 环境变量配置 ==============
# 在导入任何模块之前设置，确保 LiteLLM 能正确调用阿里云 API
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

if DASHSCOPE_API_KEY:
    # 设置 LiteLLM 需要的环境变量
    os.environ["OPENAI_API_KEY"] = DASHSCOPE_API_KEY
    os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
else:
    print("⚠️  请设置阿里云API Key:")
    print("   export DASHSCOPE_API_KEY=your-api-key")
    print("   或")
    print("   export OPENAI_API_KEY=your-api-key")

# ============== 导入模块 ==============
# 必须在设置环境变量之后导入
from pageindex.vision_pageindex import (
    VisionPageIndexClient,
    extract_pdf_page_images,
    generate_page_summaries_batch,
    call_vlm_async,
    answer_with_vlm,
    create_vision_agent,
    create_vision_agent_tools,
    create_chat_completions_model_provider,
    batch_retrieve_for_requirements,
    generate_retrieval_report,
    get_page_images_for_range,
)
from pageindex.utils import llm_completion, extract_json


# ============== 示例1: 基础使用 ==============

def example_basic_usage(pdf_path: str, query: str):
    """
    基础使用示例：一站式处理扫描件PDF查询
    """
    print("\n" + "="*60)
    print("示例1: 基础使用")
    print("="*60)

    # 初始化客户端
    client = VisionPageIndexClient(
        text_model="qwen3.5-flash",
        vision_model="qwen3-vl-flash",
        api_key=DASHSCOPE_API_KEY
    )

    print(f"\n📄 处理PDF: {pdf_path}")

    # 索引扫描件
    doc_id = client.index_scanned_pdf(pdf_path)
    print(f"✅ 索引完成，doc_id: {doc_id}")

    # 获取文档信息
    doc_info = json.loads(client.get_document(doc_id))
    print(f"\n📖 文档信息:")
    print(f"   名称: {doc_info.get('doc_name')}")
    print(f"   页数: {doc_info.get('page_count')}")
    print(f"   描述: {doc_info.get('doc_description', '')[:50]}...")

    # 检索
    print(f"\n🔍 查询: {query}")
    result = client.retrieve_with_vlm(doc_id, query)

    print(f"\n📍 定位页码: {result.get('page_ranges')}")
    print(f"\n💡 答案:")
    print(result.get('answer', ''))

    return result


# ============== 示例2: 分步处理 ==============

def example_step_by_step(pdf_path: str):
    """
    分步处理示例：展示每个步骤的细节
    """
    print("\n" + "="*60)
    print("示例2: 分步处理")
    print("="*60)

    # Step 1: PDF转图片
    print("\n📌 Step 1: PDF转图片")
    output_dir = os.path.join(os.path.dirname(pdf_path), "output_images")
    page_images = extract_pdf_page_images(pdf_path, output_dir, zoom=2.0)
    print(f"   输出目录: {output_dir}")
    print(f"   图片数量: {len(page_images)}")

    # Step 2: VLM生成摘要
    print("\n📌 Step 2: VLM生成页面摘要")
    print("   (使用 qwen3-vl-flash 处理图片)")

    summaries = asyncio.run(generate_page_summaries_batch(
        page_images,
        model="qwen3-vl-flash",
        max_length=200,
        batch_size=5
    ))

    print(f"   摘要数量: {len(summaries)}")
    for page, summary in list(summaries.items())[:3]:
        print(f"   第{page}页: {summary[:80]}...")

    # Step 3: 初始化客户端
    print("\n📌 Step 3: 初始化Vision客户端")
    client = VisionPageIndexClient(
        text_model="qwen3.5-flash",
        vision_model="qwen3-vl-flash",
        api_key=DASHSCOPE_API_KEY,
        workspace="./example_workspace"
    )

    # Step 4: 索引（跳过摘要生成，因为已生成）
    print("\n📌 Step 4: 索引扫描件")
    doc_id = client.index_scanned_pdf(pdf_path, generate_summaries=False)
    # 手动设置摘要
    client.page_summaries[doc_id] = summaries

    print(f"   doc_id: {doc_id}")

    # Step 5: 获取结构
    print("\n📌 Step 5: 查看文档结构")
    structure = json.loads(client.get_document_structure(doc_id))
    print(f"   顶级节点数: {len(structure)}")
    for node in structure[:3]:
        print(f"   [{node.get('node_id')}] {node.get('title')} (页码: {node.get('start_index')}-{node.get('end_index')})")

    # Step 6: 检索示例
    print("\n📌 Step 6: 执行检索")
    query = "请找出文档中的关键技术方案"
    result = client.retrieve_with_vlm(doc_id, query, max_images=3)

    print(f"   查询: {query}")
    print(f"   定位页码: {result.get('page_ranges')}")
    print(f"   图片数量: {len(result.get('image_paths', []))}")

    return client, doc_id


# ============== 示例3: Agent检索 ==============

def example_agent_retrieval(pdf_path: str, query: str):
    """
    Agent检索示例：使用OpenAI Agents SDK进行智能检索

    支持 workspace 缓存，避免重复生成索引
    """
    print("\n" + "="*60)
    print("示例3: Agent检索")
    print("="*60)

    # 检查是否安装了openai-agents
    try:
        from agents import Agent, Runner, RunConfig, function_tool
    except ImportError:
        print("⚠️  需要安装 openai-agents: pip install openai-agents")
        print("   跳过Agent示例，使用工具函数方式...")
        return example_tools_based_retrieval(pdf_path, query)

    print("\n🤖 创建Vision Agent...")

    # 使用 workspace 缓存索引结果
    workspace_dir = os.path.join(os.path.dirname(pdf_path), ".pageIndex_workspace")
    print(f"   Workspace: {workspace_dir}")

    # 初始化客户端
    client = VisionPageIndexClient(
        text_model="qwen3.5-flash",
        vision_model="qwen3-vl-flash",
        api_key=DASHSCOPE_API_KEY,
        workspace=workspace_dir  # 设置 workspace 以启用缓存
    )

    # 使用 get_or_create_index 复用已有索引
    print(f"\n📄 处理PDF: {pdf_path}")
    doc_id = client.get_or_create_index(pdf_path)
    print(f"   文档ID: {doc_id}")

    # 创建Agent
    agent = create_vision_agent(client, doc_id)

    # 创建 Chat Completions ModelProvider（兼容阿里云 API）
    model_provider = create_chat_completions_model_provider(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    print(f"\n🔍 执行Agent查询: {query}")

    # 配置：禁用 tracing + 使用 Chat Completions API
    run_config = RunConfig(
        tracing_disabled=True,
        model_provider=model_provider
    )

    # 运行Agent（Runner.run 是异步方法）
    result = asyncio.run(Runner.run(agent, query, run_config=run_config, max_turns=10))

    print(f"\n💡 Agent输出:")
    # 获取最终输出
    if hasattr(result, 'final_output') and result.final_output:
        print(result.final_output)
    else:
        # 如果 final_output 为空，尝试从 raw_responses 提取
        for resp in result.raw_responses:
            for item in resp.output:
                if hasattr(item, 'content'):
                    for content in item.content:
                        if hasattr(content, 'text'):
                            print(content.text)

    return result


# ============== 示例4: 工具函数方式 ==============

def example_tools_based_retrieval(pdf_path: str, query: str):
    """
    工具函数方式：不依赖openai-agents，直接使用工具函数

    优先使用关键词定位策略（两阶段定位）
    """
    print("\n" + "="*60)
    print("示例4: 工具函数检索")
    print("="*60)

    # 初始化客户端
    client = VisionPageIndexClient(
        text_model="qwen3.5-flash",
        vision_model="qwen3-vl-flash",
        api_key=DASHSCOPE_API_KEY
    )

    # 索引文档
    doc_id = client.index_scanned_pdf(pdf_path)

    print("\n🔍 执行检索流程:")

    # 方式1: 使用 retrieve_with_vlm 方法（优先使用关键词定位）
    print("\n   使用 retrieve_with_vlm 方法进行检索...")
    result = client.retrieve_with_vlm(doc_id, query)

    print(f"\n   定位方法: {result.get('location_method', 'unknown')}")
    print(f"   定位页码: {result.get('page_ranges', [])}")

    if result.get('title_pages'):
        print(f"   标题页（包含关键词）: {result.get('title_pages')}")
    if result.get('material_pages'):
        print(f"   证明材料页: {result.get('material_pages')}")

    print(f"\n   定位理由: {result.get('reason', '')[:100]}...")

    # VLM答案
    print(f"\n💡 VLM答案:")
    print(result.get('answer', ''))

    return result


# ============== 示例5: 批量检索（采购文件场景）=============

def example_batch_retrieval(pdf_path: str, requirements_file: str = None):
    """
    批量检索示例：针对采购文件的多项要求进行批量检索

    适用场景：
    - 采购文件有多项技术要求
    - 需要验证响应文件是否满足每项要求
    - 生成检索报告
    """
    print("\n" + "="*60)
    print("示例5: 批量检索（采购文件场景）")
    print("="*60)

    # 定义采购要求（可从文件读取）
    if requirements_file and os.path.exists(requirements_file):
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = [line.strip() for line in f if line.strip()]
    else:
        # 示例要求
        requirements = [
            "技术方案设计说明",
            "项目实施计划及时间安排",
            "人员配置方案",
            "售后服务承诺",
            "资质证书及证明材料",
        ]

    print(f"\n📋 采购要求列表 ({len(requirements)}项):")
    for i, req in enumerate(requirements, 1):
        print(f"   {i}. {req}")

    # 初始化客户端
    client = VisionPageIndexClient(
        text_model="qwen3.5-flash",
        vision_model="qwen3-vl-flash",
        api_key=DASHSCOPE_API_KEY
    )

    # 索引响应文件
    print(f"\n📄 处理响应文件: {pdf_path}")
    doc_id = client.index_scanned_pdf(pdf_path)

    # 批量检索
    print("\n🔍 开始批量检索...")
    results = asyncio.run(batch_retrieve_for_requirements(
        client, doc_id, requirements, max_images_per_req=3
    ))

    # 生成报告
    print("\n📊 生成检索报告...")
    report = generate_retrieval_report(results)

    # 输出报告
    print("\n" + "="*60)
    print("检索报告")
    print("="*60)
    print(report)

    # 保存报告
    report_path = os.path.join(os.path.dirname(pdf_path), "检索报告.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {report_path}")

    return results


# ============== 示例6: VLM直接处理图片 ==============

def example_vlm_direct(image_dir: str, query: str):
    """
    VLM直接处理图片示例：已有图片目录，直接查询
    """
    print("\n" + "="*60)
    print("示例6: VLM直接处理图片")
    print("="*60)

    # 收集图片
    image_paths = []
    for f in sorted(os.listdir(image_dir)):
        if f.endswith(('.jpg', '.jpeg', '.png')):
            image_paths.append(os.path.join(image_dir, f))

    print(f"\n📁 图片目录: {image_dir}")
    print(f"   图片数量: {len(image_paths)}")

    if not image_paths:
        print("⚠️  目录中没有图片文件")
        return

    # 直接使用VLM处理
    print(f"\n🔍 查询: {query}")
    print("   使用 qwen3-vl-flash 直接处理图片...")

    answer = asyncio.run(answer_with_vlm(query, image_paths[:5], "qwen3-vl-flash"))

    print(f"\n💡 答案:")
    print(answer)

    return answer


# ============== 主函数 ==============

def main():
    parser = argparse.ArgumentParser(description="扫描件PDF智能检索示例")
    parser.add_argument("--pdf", type=str, help="PDF文件路径")
    parser.add_argument("--query", type=str, default="请总结文档主要内容", help="查询问题")
    parser.add_argument("--image-dir", type=str, help="图片目录路径（已有图片）")
    parser.add_argument("--requirements", type=str, help="采购要求文件路径")
    parser.add_argument("--example", type=int, default=1, help="示例编号(1-6)")

    args = parser.parse_args()

    # 检查API Key
    if not DASHSCOPE_API_KEY:
        print("请设置API Key后运行:")
        print("  export DASHSCOPE_API_KEY=your-key")
        return

    # 选择示例
    examples = {
        1: lambda: example_basic_usage(args.pdf, args.query) if args.pdf else print("需要 --pdf 参数"),
        2: lambda: example_step_by_step(args.pdf) if args.pdf else print("需要 --pdf 参数"),
        3: lambda: example_agent_retrieval(args.pdf, args.query) if args.pdf else print("需要 --pdf 参数"),
        4: lambda: example_tools_based_retrieval(args.pdf, args.query) if args.pdf else print("需要 --pdf 参数"),
        5: lambda: example_batch_retrieval(args.pdf, args.requirements) if args.pdf else print("需要 --pdf 参数"),
        6: lambda: example_vlm_direct(args.image_dir, args.query) if args.image_dir else print("需要 --image-dir 参数"),
    }

    if args.example in examples:
        examples[args.example]()
    else:
        print(f"示例编号 {args.example} 不存在，请选择 1-6")


if __name__ == "__main__":
    # 如果没有命令行参数，运行交互式演示
    if len(sys.argv) == 1:
        print("\n" + "="*60)
        print("扫描件PDF智能检索演示")
        print("="*60)
        print("\n使用方式:")
        print("  python example_vision_retrieval.py --pdf 文件.pdf --query 查询内容")
        print("\n示例选项 (--example N):")
        print("  1. 基础使用 - 一站式处理")
        print("  2. 分步处理 - 展示每个步骤")
        print("  3. Agent检索 - 使用OpenAI Agents SDK")
        print("  4. 工具函数 - 不依赖Agents SDK")
        print("  5. 批量检索 - 采购文件场景")
        print("  6. VLM直接 - 处理已有图片")

        print("\n前置条件:")
        print("  export DASHSCOPE_API_KEY=your-api-key")
        print("  pip install litellm pymupdf openai-agents")

        # 示例参数
        print("\n示例命令:")
        print("  # 基础使用")
        print("  python example_vision_retrieval.py --pdf 响应文件.pdf --query '技术方案' --example 1")
        print("\n  # 批量检索")
        print("  python example_vision_retrieval.py --pdf 响应文件.pdf --example 5")
    else:
        main()