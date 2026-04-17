"""
采购评分项知识库构建测试

测试知识库构建工具和扩展检索功能

运行方式:
    python tests/test_procurement_kb.py

依赖:
    - pageindex.procurement_knowledge: 核心知识库
    - pageindex.procurement_kb_builder: 构建工具
    - pageindex.vision_pageindex: 扩展检索
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pageindex.procurement_knowledge import (
    ProcurementKnowledgeBase,
    PROCUREMENT_REQUIREMENTS_KNOWLEDGE,
    expand_page_range,
    format_retrieval_result
)
from pageindex.procurement_kb_builder import (
    TenderParser,
    KeywordDiscovery,
    KBValidator,
    KBManager,
    ExpertKBEnricher,
    quick_build_kb
)


def test_knowledge_base():
    """测试基础知识库功能"""
    print("\n" + "="*60)
    print("测试1: 基础知识库功能")
    print("="*60)

    kb = ProcurementKnowledgeBase()

    # 测试意图解析
    queries = ["人员配备", "类似业绩", "设备能力", "技术方案", "报价响应"]

    for query in queries:
        intent = kb.parse_intent(query)
        print(f"\n查询: '{query}'")
        print(f"  - 类型: {intent.get('requirement_type')}")
        print(f"  - 类别: {intent.get('category')}")
        print(f"  - 匹配关键词: {intent.get('matched_keywords', [])[:3]}")
        print(f"  - 置信度: {intent.get('confidence', 0):.2f}")

        # 获取证明材料关键词
        materials = kb.get_material_keywords(intent.get('requirement_type', query))
        if materials:
            print(f"  - 证明材料关键词: {materials[:5]}")

    # 测试获取所有类型
    all_types = kb.get_all_requirement_types()
    print(f"\n支持的评分项类型: {all_types}")

    return kb


def test_expert_enricher():
    """测试专家知识注入"""
    print("\n" + "="*60)
    print("测试2: 专家知识注入器")
    print("="*60)

    # 创建基础知识库字典
    kb_dict = {
        "kb_type": "test",
        "requirements": PROCUREMENT_REQUIREMENTS_KNOWLEDGE.copy()
    }

    # 专家注入
    enricher = ExpertKBEnricher(kb_dict)

    # 添加新的证明材料类型
    enricher.add_material_type(
        requirement_type="人员配备",
        material_type="健康证明",
        keywords=["健康证", "体检证明", "健康证明书"],
        description="作业人员健康证明",
        multi_page=False
    )

    # 添加排除关键词
    enricher.add_exclude_keywords(
        requirement_type="类似业绩",
        keywords=["业绩偏离表", "业绩响应表"]
    )

    # 添加标题关键词
    enricher.add_title_keywords(
        requirement_type="人员配备",
        keywords=["人员一览表", "人员情况"]
    )

    # 查看更新后的知识库
    updated_kb = enricher.get_kb_dict()

    print("\n人员配备 - 新增材料类型:")
    materials = updated_kb["requirements"]["人员配备"]["material_types"]
    print(f"  健康证明: {materials.get('健康证明', {})}")

    print("\n类似业绩 - 排除关键词:")
    exclude = updated_kb["requirements"]["类似业绩"].get("exclude_keywords", [])
    print(f"  {exclude}")

    return updated_kb


def test_kb_manager():
    """测试知识库管理器"""
    print("\n" + "="*60)
    print("测试3: 知识库管理器")
    print("="*60)

    workspace = Path(__file__).parent / "kb_workspace"
    workspace.mkdir(exist_ok=True)

    manager = KBManager(str(workspace))

    # 创建并保存知识库
    kb_dict = {
        "kb_id": "kb_test_001",
        "version": "1.0.0",
        "requirements": PROCUREMENT_REQUIREMENTS_KNOWLEDGE.copy()
    }

    saved_path = manager.save("kb_test_v1.json", kb_dict)
    print(f"\n知识库已保存: {saved_path}")

    # 加载知识库
    loaded_kb = manager.load("kb_test_v1.json")
    print(f"知识库已加载，包含评分项: {list(loaded_kb['requirements'].keys())}")

    # 创建知识库实例
    kb_instance = manager.create_kb_instance(loaded_kb)
    intent = kb_instance.parse_intent("人员配备")
    print(f"\n从加载的知识库解析 '人员配备': {intent.get('requirement_type')}")

    # 列出所有知识库
    all_kbs = manager.list_kbs()
    print(f"\n工作区知识库列表: {all_kbs}")

    return manager


def test_keyword_discovery():
    """测试关键词发现器"""
    print("\n" + "="*60)
    print("测试4: 关键词发现器")
    print("="*60)

    kb = ProcurementKnowledgeBase()
    discovery = KeywordDiscovery(kb)

    # 模拟页面摘要
    mock_summaries = {
        85: "人员配备方案，包含项目经理和技术人员配置表",
        86: "人员名单，张三、李四、王五的基本信息",
        87: "操作手合格证，无人机飞手资质证书，大疆认证",
        88: "植保无人机操作证，飞手培训合格证",
        89: "健康证明，体检报告，作业人员健康检查",
        90: "技术方案部分，作业流程设计",
    }

    # 发现关键词
    result = discovery.discover_from_summaries(
        page_summaries=mock_summaries,
        requirement_type="人员配备",
        known_material_pages=[87, 88, 89],
        min_frequency=1
    )

    print(f"\n评分项: {result['requirement_type']}")
    print(f"发现的新关键词: {result['new_keywords'][:5]}")
    print(f"建议材料类型: {result['suggested_material_type']}")
    print(f"置信度: {result['confidence']}")

    # 补充知识库
    kb_dict = {"requirements": PROCUREMENT_REQUIREMENTS_KNOWLEDGE.copy()}
    enriched = discovery.enrich_kb_with_discovery(kb_dict, result)
    print(f"\n补充后的材料类型: {enriched['requirements']['人员配备']['material_types'].keys()}")

    return discovery


def test_kb_validator():
    """测试知识库验证器"""
    print("\n" + "="*60)
    print("测试5: 知识库验证器")
    print("="*60)

    kb = ProcurementKnowledgeBase()
    validator = KBValidator(kb)

    # 模拟页面摘要
    mock_summaries = {
        85: "人员配备方案，项目人员配置表",
        87: "操作手合格证，无人机操作证",
        88: "飞手证，培训合格证",
        89: "健康证明",
        64: "类似业绩一览表",
        65: "中标通知书",
        66: "政府采购合同",
        67: "验收报告",
    }

    # 标注数据
    ground_truth = [
        {"query": "人员配备", "expected_pages": [85, 87, 88, 89]},
        {"query": "类似业绩", "expected_pages": [64, 65, 66, 67]},
    ]

    # 验证
    report = validator.validate_with_ground_truth(
        ground_truth=ground_truth,
        page_summaries=mock_summaries
    )

    print(f"\n验证摘要:")
    print(f"  总查询数: {report['summary']['total_queries']}")
    print(f"  平均召回率: {report['summary']['avg_recall']:.2f}")
    print(f"  平均精确率: {report['summary']['avg_precision']:.2f}")
    print(f"  F1分数: {report['summary']['f1_score']:.2f}")

    print(f"\n详细结果:")
    for detail in report['details']:
        print(f"  [{detail['query']}]")
        print(f"    - 期望页面: {detail['expected_pages']}")
        print(f"    - 检测页面: {detail['detected_pages']}")
        print(f"    - 召回率: {detail['recall']:.2f}, 精确率: {detail['precision']:.2f}")

    print(f"\n优化建议:")
    for rec in report['recommendations']:
        print(f"  {rec}")

    return report


def test_page_range_merge():
    """测试页码范围合并"""
    print("\n" + "="*60)
    print("测试6: 页码范围合并")
    print("="*60)

    # 测试不同场景
    test_cases = [
        {
            "name": "连续范围",
            "title_pages": [87],
            "material_pages": [88, 89],
            "expected": ["87-89"]
        },
        {
            "name": "分散范围",
            "title_pages": [64],
            "material_pages": [65, 66, 67, 68],
            "expected": ["64-68"]
        },
        {
            "name": "多个标题页",
            "title_pages": [85, 94],
            "material_pages": [86, 87, 95],
            "expected": ["85-87", "94-95"]
        },
        {
            "name": "单页",
            "title_pages": [42],
            "material_pages": [],
            "expected": ["42"]
        },
    ]

    for tc in test_cases:
        result = expand_page_range(
            tc["title_pages"],
            tc["material_pages"],
            merge_adjacent=True,
            max_gap=1
        )
        status = "✓" if result == tc["expected"] else "✗"
        print(f"\n{status} {tc['name']}:")
        print(f"  输入: 标题={tc['title_pages']}, 材料={tc['material_pages']}")
        print(f"  输出: {result}")
        print(f"  期望: {tc['expected']}")


def test_format_result():
    """测试结果格式化"""
    print("\n" + "="*60)
    print("测试7: 检索结果格式化")
    print("="*60)

    # 模拟检索结果
    result = format_retrieval_result(
        requirement_type="人员配备",
        title_pages=[87],
        material_pages=[88, 89],
        material_details=[
            {"page": 88, "material_type": "操作证", "matched_keywords": ["操作手合格证"]},
            {"page": 89, "material_type": "健康证明", "matched_keywords": ["健康证"]},
        ]
    )

    print(result)


def test_tender_parser():
    """测试采购文件解析器"""
    print("\n" + "="*60)
    print("测试8: 采购文件解析器（模拟输入）")
    print("="*60)

    parser = TenderParser()

    # 模拟采购文件文本
    mock_tender_text = """
    松滋市2026年小麦一喷三防飞防服务采购项目

    第四章 评分标准

    一、综合评分法，总分100分

    评分项目：
    1. 价格分（30分）
       以满足招标文件要求的最低报价为基准

    2. 技术分（40分）
       (1) 技术方案（20分）
           评审内容：作业方案设计、技术措施
       (2) 人员配备（10分）
           评审内容：操作人员数量、资质证书
           证明材料：操作手合格证、培训证明
       (3) 设备能力（10分）
           评审内容：无人机数量、型号
           证明材料：设备发票

    3. 商务分（30分）
       (1) 类似业绩（15分）
           评审内容：近三年同类项目业绩
           证明材料：中标通知书、合同、验收报告
       (2) 企业资质（10分）
           评审内容：营业执照、相关资质
       (3) 信誉荣誉（5分）
           评审内容：荣誉证书、信用等级
    """

    result = parser.extract_from_tender(
        tender_file=None,
        text_content=mock_tender_text,
        base_kb=ProcurementKnowledgeBase()
    )

    print(f"\n项目名称: {result.get('tender_name', '未识别')}")
    print(f"评分方法: {result.get('evaluation_method', '未识别')}")
    print(f"总分: {result.get('total_score', 100)}")
    print(f"\n提取的评分项:")
    for req_type, config in result.get('requirements', {}).items():
        print(f"  [{req_type}] ({config.get('score', 0)}分)")
        print(f"    类别: {config.get('category')}")
        print(f"    来源: {config.get('source')}")

    return result


def test_quick_build():
    """测试快速构建函数"""
    print("\n" + "="*60)
    print("测试9: 快速构建知识库")
    print("="*60)

    # 专家补充输入
    expert_input = {
        "人员配备": {
            "add_materials": {
                "健康证明": ["健康证", "体检报告", "健康证明书"]
            },
            "add_exclude": ["人员偏离表"]
        },
        "类似业绩": {
            "add_exclude": ["业绩偏离表", "业绩响应表"]
        }
    }

    kb = quick_build_kb(
        tender_text=None,
        expert_input=expert_input
    )

    # 测试构建的知识库
    intent = kb.parse_intent("人员配备")
    print(f"\n解析 '人员配备':")
    print(f"  类型: {intent.get('requirement_type')}")
    print(f"  排除词: {intent.get('exclude_keywords', [])}")

    materials = kb.get_material_keywords("人员配备")
    print(f"  证明材料关键词: {materials}")

    return kb


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("采购评分项知识库构建工具 - 综合测试")
    print("="*60)

    try:
        test_knowledge_base()
        test_expert_enricher()
        test_kb_manager()
        test_keyword_discovery()
        test_kb_validator()
        test_page_range_merge()
        test_format_result()
        test_tender_parser()
        test_quick_build()

        print("\n" + "="*60)
        print("所有测试完成 ✓")
        print("="*60)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()