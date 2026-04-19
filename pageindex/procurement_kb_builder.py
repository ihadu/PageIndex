"""
采购评分项知识库构建工具

企业级知识库构建、验证、优化的完整工具链

使用方式：
    from pageindex.procurement_kb_builder import (
        TenderParser,          # 从采购文件提取评分项
        KeywordDiscovery,      # 从摘要发现关键词
        KBValidator,           # 知识库验证
        KBManager,             # 知识库管理
    )

    # 从采购文件提取
    parser = TenderParser()
    project_kb = parser.extract_from_tender("采购文件.pdf")

    # 关键词发现
    discovery = KeywordDiscovery(project_kb)
    new_keywords = discovery.discover_from_summaries(page_summaries)

    # 验证
    validator = KBValidator(project_kb)
    report = validator.validate_with_ground_truth(ground_truth)
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import Counter
import logging

# 兼容导入
try:
    from .utils import llm_completion, extract_json
    from .procurement_knowledge import ProcurementKnowledgeBase, PROCUREMENT_REQUIREMENTS_KNOWLEDGE
except ImportError:
    from utils import llm_completion, extract_json
    from procurement_knowledge import ProcurementKnowledgeBase, PROCUREMENT_REQUIREMENTS_KNOWLEDGE

logger = logging.getLogger(__name__)


# ============== 工具1: 采购文件解析器 ==============

class TenderParser:
    """
    从采购文件（招标文件）中自动提取评分项

    工作流程：
    1. 读取采购文件内容（PDF转文本或已有摘要）
    2. 使用LLM识别评分标准部分
    3. 提取评分项名称、分值、评审要求
    4. 映射到已有知识库结构

    示例：
        parser = TenderParser()
        result = parser.extract_from_tender(
            tender_file="采购文件.pdf",
            base_kb=existing_kb  # 可选，基于已有知识库
        )
    """

    def __init__(self, model: str = "qwen3.5-flash"):
        self.model = model

    def extract_from_tender(
        self,
        tender_file: str,
        base_kb: ProcurementKnowledgeBase = None,
        text_content: str = None
    ) -> Dict:
        """
        从采购文件提取评分项

        Args:
            tender_file: 采购文件路径（或提供text_content）
            base_kb: 已有知识库（用于映射）
            text_content: 直接提供文本内容（可选）

        Returns:
            提取的评分项结构
        """
        # 获取文件内容
        if text_content:
            content = text_content
        elif os.path.exists(tender_file):
            # 尝试读取PDF文本或摘要
            content = self._read_tender_content(tender_file)
        else:
            raise FileNotFoundError(f"文件不存在: {tender_file}")

        # 使用LLM提取评分标准
        json_example = '''
{
  "tender_name": "项目名称",
  "evaluation_method": "综合评分法/最低价中标",
  "total_score": 100,
  "requirements": [
    {
      "name": "人员配备",
      "score": 10,
      "criteria": "评审要求描述",
      "materials": ["操作证", "培训证明"],
      "keywords_from_criteria": ["关键词1", "关键词2"]
    }
  ]
}
'''
        prompt = f"""请从以下采购文件内容中提取评分标准。

采购文件内容：
{content[:5000]}

请提取：
1. 评分项名称
2. 各项分值
3. 评审要求（证明材料要求）
4. 评分标准详情

返回JSON格式：
```json
{json_example}
```

注意：只提取评分部分，不要包含无关内容。
"""
        response = llm_completion(self.model, prompt)
        extracted = extract_json(response)

        if not extracted:
            logger.warning("LLM提取失败，返回空结构")
            extracted = {"requirements": []}

        # 映射到知识库结构
        if base_kb:
            mapped_kb = self._map_to_kb_structure(extracted, base_kb)
        else:
            mapped_kb = self._create_kb_structure(extracted)

        return mapped_kb

    def _read_tender_content(self, tender_file: str) -> str:
        """读取采购文件内容"""
        # 尝试读取PDF
        try:
            import fitz
            doc = fitz.open(tender_file)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logger.warning(f"PDF读取失败: {e}")
            return ""

    def _map_to_kb_structure(
        self,
        extracted: Dict,
        base_kb: ProcurementKnowledgeBase
    ) -> Dict:
        """将提取的评分项映射到已有知识库结构"""
        requirements = extracted.get("requirements", [])
        mapped_requirements = {}

        for req in requirements:
            name = req.get("name")
            score = req.get("score", 0)
            criteria = req.get("criteria", "")
            materials = req.get("materials", [])

            # 尝试映射到已有类型
            intent = base_kb.parse_intent(name)

            if intent.get("requirement_type") != "unknown":
                # 已有类型，继承结构
                req_type = intent["requirement_type"]
                mapped_requirements[req_type] = {
                    "category": intent.get("category"),
                    "score": score,
                    "criteria": criteria,
                    "title_keywords": intent.get("title_keywords", []),
                    "material_types": intent.get("material_types", {}),
                    "additional_materials": materials,  # 新增材料类型
                    "source": "tender_extracted"
                }
            else:
                # 新类型，创建结构
                mapped_requirements[name] = {
                    "category": self._infer_category(name),
                    "score": score,
                    "criteria": criteria,
                    "title_keywords": [name],
                    "material_types": {},
                    "source": "tender_extracted",
                    "needs_enrichment": True  # 标记需要补充
                }

        return {
            "kb_type": "project_specific",
            "tender_name": extracted.get("tender_name", ""),
            "evaluation_method": extracted.get("evaluation_method", ""),
            "total_score": extracted.get("total_score", 100),
            "requirements": mapped_requirements
        }

    def _create_kb_structure(self, extracted: Dict) -> Dict:
        """创建新的知识库结构"""
        requirements = extracted.get("requirements", [])
        kb_requirements = {}

        for req in requirements:
            name = req.get("name")
            kb_requirements[name] = {
                "category": self._infer_category(name),
                "score": req.get("score", 0),
                "criteria": req.get("criteria", ""),
                "title_keywords": [name],
                "material_types": {},
                "keywords_from_criteria": req.get("keywords_from_criteria", []),
                "source": "tender_extracted",
                "needs_enrichment": True
            }

        return {
            "kb_type": "project_specific",
            "tender_name": extracted.get("tender_name", ""),
            "requirements": kb_requirements
        }

    def _infer_category(self, name: str) -> str:
        """推断评分项类别"""
        category_keywords = {
            "人员类": ["人员", "团队", "配备", "配置", "作业人员", "技术人员"],
            "业绩类": ["业绩", "业绩证明", "类似业绩", "项目经历"],
            "资质类": ["资质", "证书", "许可", "认证"],
            "技术类": ["技术", "方案", "设计", "实施"],
            "商务类": ["商务", "价格", "报价", "服务", "售后"],
            "设备类": ["设备", "机械", "仪器", "无人机"],
            "财务类": ["财务", "资金", "审计"],
            "信誉类": ["信誉", "荣誉", "信用"],
        }

        for category, keywords in category_keywords.items():
            for kw in keywords:
                if kw in name:
                    return category

        return "其他"


# ============== 工具2: 关键词发现器 ==============

class KeywordDiscovery:
    """
    从页面摘要中自动发现证明材料关键词

    工作流程：
    1. 分析已知证明材料页的摘要
    2. 统计高频关键词
    3. 排除已有关键词
    4. LLM归纳新关键词

    示例：
        discovery = KeywordDiscovery(kb)
        new_keywords = discovery.discover_from_summaries(
            page_summaries={87: "...", 88: "..."},
            requirement_type="人员配备"
        )
    """

    def __init__(self, kb: ProcurementKnowledgeBase, model: str = "qwen3.5-flash"):
        self.kb = kb
        self.model = model

    def discover_from_summaries(
        self,
        page_summaries: Dict[int, str],
        requirement_type: str,
        known_material_pages: List[int] = None,
        min_frequency: int = 2
    ) -> Dict:
        """
        从摘要发现新关键词

        Args:
            page_summaries: 页码到摘要的映射
            requirement_type: 评分项类型
            known_material_pages: 已知的证明材料页（可选）
            min_frequency: 最小出现频率

        Returns:
            {
                "new_keywords": [...],
                "keyword_frequency": {...},
                "suggested_material_type": "...",
                "confidence": 0.8
            }
        """
        # 获取已有关键词
        existing_keywords = self.kb.get_material_keywords(requirement_type)

        # 如果没有提供已知证明材料页，使用统计方法发现
        if not known_material_pages:
            # 假设证明材料页在文档后半部分
            all_pages = sorted(page_summaries.keys())
            if len(all_pages) > 10:
                candidate_pages = all_pages[int(len(all_pages) * 0.6):]
            else:
                candidate_pages = all_pages
        else:
            candidate_pages = known_material_pages

        # 统计关键词频率
        keyword_counter = Counter()

        for page in candidate_pages:
            summary = page_summaries.get(page, "")
            if not summary:
                continue

            # 提取关键词（简单分词）
            words = re.findall(r'[\w\u4e00-\u9fff]+', summary)
            for word in words:
                if len(word) >= 2:  # 至少2个字符
                    keyword_counter[word] += 1

        # 过滤：排除已有关键词和低频词
        new_keywords = []
        for word, freq in keyword_counter.most_common(50):
            if freq >= min_frequency and word not in existing_keywords:
                # 排除通用词
                if word not in ["页面", "文档", "显示", "包含", "该", "此", "为", "有"]:
                    new_keywords.append({
                        "keyword": word,
                        "frequency": freq,
                        "pages": self._find_pages_with_keyword(page_summaries, word)
                    })

        # 使用LLM归纳关键词类型
        if new_keywords:
            suggested_type = self._infer_material_type(new_keywords[:10], requirement_type)
        else:
            suggested_type = None

        return {
            "requirement_type": requirement_type,
            "new_keywords": new_keywords[:20],
            "keyword_frequency": dict(keyword_counter.most_common(20)),
            "suggested_material_type": suggested_type,
            "existing_keywords": existing_keywords,
            "confidence": len(new_keywords) / 10 if new_keywords else 0
        }

    def _find_pages_with_keyword(self, page_summaries: Dict, keyword: str) -> List[int]:
        """找到包含关键词的页面"""
        pages = []
        for page, summary in page_summaries.items():
            if keyword in summary:
                pages.append(page)
        return pages

    def _infer_material_type(self, keywords: List, requirement_type: str) -> Optional[str]:
        """推断证明材料类型"""
        # 材料类型关键词模式
        material_patterns = {
            "操作证": ["操作证", "合格证", "操作手", "飞手证", "驾驶证"],
            "合同": ["合同", "协议", "采购合同", "服务合同"],
            "发票": ["发票", "增值税", "收据"],
            "证书": ["证书", "认证", "资质证书"],
            "报告": ["报告", "验收", "审计"],
            "通知": ["通知", "中标", "成交"],
            "证明": ["证明", "证明函", "说明"],
        }

        keyword_names = [k["keyword"] for k in keywords]

        for material_type, patterns in material_patterns.items():
            match_count = sum(1 for kw in keyword_names if any(p in kw for p in patterns))
            if match_count >= 2:
                return material_type

        return None

    def enrich_kb_with_discovery(
        self,
        kb_dict: Dict,
        discovery_result: Dict
    ) -> Dict:
        """用发现结果补充知识库"""
        requirement_type = discovery_result["requirement_type"]
        new_keywords = discovery_result["new_keywords"]
        suggested_type = discovery_result["suggested_material_type"]

        if requirement_type not in kb_dict.get("requirements", {}):
            return kb_dict

        req_config = kb_dict["requirements"][requirement_type]

        # 如果有建议的材料类型
        if suggested_type:
            if suggested_type not in req_config.get("material_types", {}):
                req_config["material_types"][suggested_type] = {
                    "keywords": [k["keyword"] for k in new_keywords[:5]],
                    "description": f"自动发现的{ suggested_type }关键词",
                    "source": "auto_discovered",
                    "frequency": sum(k["frequency"] for k in new_keywords[:5])
                }
            else:
                # 补充已有类型的关键词
                existing = req_config["material_types"][suggested_type].get("keywords", [])
                for nk in new_keywords[:5]:
                    if nk["keyword"] not in existing:
                        existing.append(nk["keyword"])

        kb_dict["requirements"][requirement_type] = req_config
        return kb_dict


# ============== 工具3: 知识库验证器 ==============

class KBValidator:
    """
    知识库验证器

    验证知识库的准确性，生成验证报告

    示例：
        validator = KBValidator(kb)
        report = validator.validate_with_ground_truth(
            ground_truth=[
                {"query": "人员配备", "expected_pages": [85, 87, 88, 89]}
            ],
            page_summaries={...}
        )
    """

    def __init__(self, kb: ProcurementKnowledgeBase):
        self.kb = kb

    def validate_with_ground_truth(
        self,
        ground_truth: List[Dict],
        page_summaries: Dict[int, str],
        client = None,
        doc_id: str = None
    ) -> Dict:
        """
        使用标注数据验证知识库

        Args:
            ground_truth: 标注数据列表
                [{"query": "人员配备", "expected_pages": [85, 87, 88, 89]}]
            page_summaries: 页面摘要
            client: VisionPageIndexClient（可选，用于实际检索）
            doc_id: 文档ID

        Returns:
            验证报告
        """
        results = []
        total_recall = 0
        total_precision = 0

        for gt in ground_truth:
            query = gt["query"]
            expected_pages = set(gt["expected_pages"])

            # 使用知识库检索
            intent = self.kb.parse_intent(query)
            material_keywords = self.kb.get_material_keywords(intent.get("requirement_type", query))

            # 模拟检索
            detected_pages = set()

            # 标题页检测
            title_keywords = intent.get("title_keywords", [query])
            for page, summary in page_summaries.items():
                for kw in title_keywords:
                    if kw in summary:
                        detected_pages.add(page)
                        break

            # 证明材料页检测
            for page, summary in page_summaries.items():
                for kw in material_keywords:
                    if kw in summary:
                        detected_pages.add(page)
                        break

            # 计算指标
            hit_pages = detected_pages & expected_pages
            recall = len(hit_pages) / len(expected_pages) if expected_pages else 0
            precision = len(hit_pages) / len(detected_pages) if detected_pages else 0

            missed_pages = expected_pages - detected_pages
            extra_pages = detected_pages - expected_pages

            results.append({
                "query": query,
                "expected_pages": sorted(expected_pages),
                "detected_pages": sorted(detected_pages),
                "hit_pages": sorted(hit_pages),
                "missed_pages": sorted(missed_pages),
                "extra_pages": sorted(extra_pages),
                "recall": recall,
                "precision": precision,
                "intent": intent.get("requirement_type", "unknown"),
                "confidence": intent.get("confidence", 0)
            })

            total_recall += recall
            total_precision += precision

        # 生成报告
        avg_recall = total_recall / len(ground_truth) if ground_truth else 0
        avg_precision = total_precision / len(ground_truth) if ground_truth else 0
        f1_score = 2 * avg_recall * avg_precision / (avg_recall + avg_precision) if (avg_recall + avg_precision) > 0 else 0

        return {
            "summary": {
                "total_queries": len(ground_truth),
                "avg_recall": avg_recall,
                "avg_precision": avg_precision,
                "f1_score": f1_score
            },
            "details": results,
            "recommendations": self._generate_recommendations(results)
        }

    def _generate_recommendations(self, results: List) -> List[str]:
        """生成优化建议"""
        recommendations = []

        for r in results:
            if r["recall"] < 0.8:
                missed = r["missed_pages"]
                if missed:
                    recommendations.append(
                        f"[{r['query']}] 漏检页面: {missed}，建议补充关键词"
                    )

            if r["precision"] < 0.7:
                extra = r["extra_pages"]
                if extra:
                    recommendations.append(
                        f"[{r['query']}] 多检页面: {extra}，建议添加排除词"
                    )

            if r["confidence"] < 0.5:
                recommendations.append(
                    f"[{r['query']}] 知识库匹配度低({r['confidence']})，建议扩展关键词"
                )

        return recommendations


# ============== 工具4: 知识库管理器 ==============

class KBManager:
    """
    知识库管理器

    功能：
    - 知识库版本管理
    - 多知识库合并
    - 导入导出
    - 工作区管理

    示例：
        manager = KBManager(workspace="./kb_workspace")

        # 保存
        manager.save("kb_v1.json", kb_dict)

        # 加载
        kb_dict = manager.load("kb_v1.json")

        # 合并
        merged = manager.merge([kb1, kb2])
    """

    def __init__(self, workspace: str = None):
        self.workspace = Path(workspace) if workspace else None
        if self.workspace:
            self.workspace.mkdir(parents=True, exist_ok=True)

    def save(self, kb_name: str, kb_dict: Dict) -> str:
        """保存知识库"""
        if self.workspace:
            kb_path = self.workspace / kb_name
        else:
            kb_path = Path(kb_name)

        kb_dict["saved_at"] = str(Path.cwd())
        kb_dict["version"] = kb_dict.get("version", "1.0.0")

        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(kb_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"知识库已保存: {kb_path}")
        return str(kb_path)

    def load(self, kb_name: str) -> Dict:
        """加载知识库"""
        if self.workspace:
            kb_path = self.workspace / kb_name
        else:
            kb_path = Path(kb_name)

        if not kb_path.exists():
            raise FileNotFoundError(f"知识库不存在: {kb_path}")

        with open(kb_path, "r", encoding="utf-8") as f:
            kb_dict = json.load(f)

        return kb_dict

    def merge(self, kb_dicts: List[Dict], merge_strategy: str = "union") -> Dict:
        """
        合并多个知识库

        Args:
            kb_dicts: 知识库列表
            merge_strategy: 合并策略
                - "union": 关键词取并集
                - "intersection": 关键词取交集
                - "weighted": 按权重合并

        Returns:
            合合后的知识库
        """
        if not kb_dicts:
            return {}

        merged = kb_dicts[0].copy()

        for kb in kb_dicts[1:]:
            for req_type, req_config in kb.get("requirements", {}).items():
                if req_type not in merged.get("requirements", {}):
                    merged["requirements"][req_type] = req_config
                else:
                    # 合并关键词
                    existing = merged["requirements"][req_type]

                    if merge_strategy == "union":
                        # 并集
                        existing["title_keywords"] = list(set(
                            existing.get("title_keywords", []) +
                            req_config.get("title_keywords", [])
                        ))
                        # 合并材料类型
                        for mat_type, mat_config in req_config.get("material_types", {}).items():
                            if mat_type not in existing.get("material_types", {}):
                                existing["material_types"][mat_type] = mat_config
                            else:
                                existing["material_types"][mat_type]["keywords"] = list(set(
                                    existing["material_types"][mat_type].get("keywords", []) +
                                    mat_config.get("keywords", [])
                                ))

        merged["merge_info"] = {
            "merged_from": len(kb_dicts),
            "strategy": merge_strategy
        }

        return merged

    def list_kbs(self) -> List[str]:
        """列出工作区的所有知识库"""
        if not self.workspace:
            return []

        return [f.name for f in self.workspace.glob("*.json")]

    def create_kb_instance(self, kb_dict: Dict) -> ProcurementKnowledgeBase:
        """从字典创建知识库实例"""
        # 转换格式
        custom_config = {}
        for req_type, config in kb_dict.get("requirements", {}).items():
            custom_config[req_type] = {
                "category": config.get("category", "其他"),
                "description": config.get("criteria", ""),
                "title_keywords": config.get("title_keywords", []),
                "exclude_keywords": config.get("exclude_keywords", []),
                "material_types": config.get("material_types", {}),
                "page_expansion_rule": config.get("page_expansion_rule", {
                    "direction": "forward",
                    "max_pages": 5
                })
            }

        return ProcurementKnowledgeBase(custom_config)


# ============== 工具5: 专家知识注入器 ==============

class ExpertKBEnricher:
    """
    专家知识注入器

    功能：
    - 从专家输入补充证明材料类型
    - 验证专家知识格式
    - 合并到现有知识库

    示例：
        enricher = ExpertKBEnricher(kb_dict)

        # 添加新的证明材料类型
        enricher.add_material_type(
            requirement_type="人员配备",
            material_type="健康证明",
            keywords=["健康证", "体检证明", "健康证明"],
            description="作业人员健康证明"
        )

        # 添加排除词
        enricher.add_exclude_keywords(
            requirement_type="类似业绩",
            keywords=["偏离表", "响应表"]
        )
    """

    def __init__(self, kb_dict: Dict):
        self.kb_dict = kb_dict

    def add_material_type(
        self,
        requirement_type: str,
        material_type: str,
        keywords: List[str],
        description: str = "",
        multi_page: bool = False
    ) -> Dict:
        """添加证明材料类型"""
        if "requirements" not in self.kb_dict:
            self.kb_dict["requirements"] = {}

        if requirement_type not in self.kb_dict["requirements"]:
            self.kb_dict["requirements"][requirement_type] = {
                "category": "其他",
                "title_keywords": [requirement_type],
                "material_types": {},
                "source": "expert_added"
            }

        req = self.kb_dict["requirements"][requirement_type]

        if "material_types" not in req:
            req["material_types"] = {}

        req["material_types"][material_type] = {
            "keywords": keywords,
            "description": description,
            "multi_page": multi_page,
            "source": "expert_added"
        }

        logger.info(f"已添加材料类型: {requirement_type} -> {material_type}")
        return self.kb_dict

    def add_exclude_keywords(
        self,
        requirement_type: str,
        keywords: List[str]
    ) -> Dict:
        """添加排除关键词"""
        if requirement_type in self.kb_dict.get("requirements", {}):
            existing = self.kb_dict["requirements"][requirement_type].get("exclude_keywords", [])
            self.kb_dict["requirements"][requirement_type]["exclude_keywords"] = list(set(existing + keywords))

        return self.kb_dict

    def add_title_keywords(
        self,
        requirement_type: str,
        keywords: List[str],
        priority: str = "secondary"
    ) -> Dict:
        """添加标题关键词"""
        if requirement_type in self.kb_dict.get("requirements", {}):
            existing = self.kb_dict["requirements"][requirement_type].get("title_keywords", [])
            self.kb_dict["requirements"][requirement_type]["title_keywords"] = list(set(existing + keywords))

        return self.kb_dict

    def get_kb_dict(self) -> Dict:
        """获取更新后的知识库"""
        return self.kb_dict


# ============== 工具6: 快速构建函数 ==============

def quick_build_kb(
    tender_file: str = None,
    tender_text: str = None,
    expert_input: Dict = None,
    output_file: str = None
) -> ProcurementKnowledgeBase:
    """
    快速构建知识库的一站式函数

    Args:
        tender_file: 采购文件路径
        tender_text: 采购文件文本内容
        expert_input: 专家补充输入
        output_file: 输出文件路径

    Returns:
        ProcurementKnowledgeBase实例

    示例：
        kb = quick_build_kb(
            tender_file="采购文件.pdf",
            expert_input={
                "人员配备": {
                    "add_materials": {
                        "健康证明": ["健康证", "体检证明"]
                    },
                    "add_exclude": ["偏离表"]
                }
            }
        )
    """
    # Step 1: 从采购文件提取
    parser = TenderParser()
    if tender_file or tender_text:
        kb_dict = parser.extract_from_tender(
            tender_file=tender_file,
            text_content=tender_text,
            base_kb=ProcurementKnowledgeBase()
        )
    else:
        # 使用默认知识库
        kb_dict = {
            "requirements": PROCUREMENT_REQUIREMENTS_KNOWLEDGE.copy()
        }

    # Step 2: 专家补充
    if expert_input:
        enricher = ExpertKBEnricher(kb_dict)
        for req_type, additions in expert_input.items():
            if "add_materials" in additions:
                for mat_type, keywords in additions["add_materials"].items():
                    enricher.add_material_type(req_type, mat_type, keywords)
            if "add_exclude" in additions:
                enricher.add_exclude_keywords(req_type, additions["add_exclude"])
            if "add_keywords" in additions:
                enricher.add_title_keywords(req_type, additions["add_keywords"])
        kb_dict = enricher.get_kb_dict()

    # Step 3: 保存
    if output_file:
        manager = KBManager()
        manager.save(output_file, kb_dict)

    # Step 4: 创建实例
    return KBManager().create_kb_instance(kb_dict)