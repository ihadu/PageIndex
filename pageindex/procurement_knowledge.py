"""
采购评分项知识库 - 政府采购响应文件评分项与证明材料标准映射

用于智能检索场景：
- 用户查询评分项时，自动识别相关证明材料页
- 解决响应文件"标题页 + 证明材料页"结构的检索难题

使用方式：
    from pageindex.procurement_knowledge import ProcurementKnowledgeBase

    kb = ProcurementKnowledgeBase()
    intent = kb.parse_intent("人员配备")
    # 返回：评分项类型、标题关键词、证明材料类型等
"""

from typing import Dict, List, Optional
import re


# ============== 采购评分项标准知识库 ==============

PROCUREMENT_REQUIREMENTS_KNOWLEDGE = {
    # 人员类评分项
    "人员配备": {
        "category": "人员类",
        "description": "项目人员配置与资质证明",
        "title_keywords": [
            "人员配备", "人员配置", "作业人员", "人员名单",
            "人员构成", "人员安排", "人员组织", "技术人员",
            "飞防作业队", "飞手配置", "操作人员"
        ],
        "material_types": {
            "操作证": {
                "keywords": ["操作手合格证", "无人机操作证", "飞手证", "植保无人机操作证", "DJI操作证", "合格证"],
                "description": "无人机操作人员资质证书",
                "multi_page": True,  # 通常多页连续
            },
            "培训证明": {
                "keywords": ["培训证明", "培训证书", "培训合格证", "培训记录"],
                "description": "人员培训相关证明",
            },
            "人员名单": {
                "keywords": ["人员名单", "人员表", "人员情况表", "人员基本情况", "人员配置表"],
                "description": "人员基本信息表格",
            },
            "职称证书": {
                "keywords": ["职称证", "职称证书", "高级职称", "中级职称", "初级职称"],
                "description": "专业技术人员职称证明",
            },
            "健康证明": {
                "keywords": ["健康证", "体检证明", "健康证明"],
                "description": "作业人员健康证明",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",  # 向后扩展
            "max_pages": 10,  # 最大扩展页数
            "stop_conditions": ["新章节标题", "下一个评分项"],
        },
        "examples": {
            "title_page": "人员配备方案/人员配置表",
            "material_pages": "后续连续的操作证、培训证明等证书页面",
        }
    },

    # 业绩类评分项
    "类似业绩": {
        "category": "业绩类",
        "description": "供应商同类项目业绩证明",
        "title_keywords": [
            "类似业绩", "业绩证明", "业绩材料", "同类业绩",
            "业绩清单", "业绩一览表", "已完工业绩", "项目业绩"
        ],
        "exclude_keywords": [
            "偏离表", "响应偏离表", "商务偏离表",  # 排除汇总表
            "响应表", "对照表", "对照一览表",  # 排除对照表
        ],
        "material_types": {
            "中标通知": {
                "keywords": ["中标通知书", "成交通知书", "中标公告", "成交公告", "中标结果"],
                "description": "项目中标/成交证明文件",
            },
            "合同": {
                "keywords": ["政府采购合同", "服务合同", "采购合同", "合同书", "协议书"],
                "description": "项目合同文件",
                "multi_page": True,
            },
            "验收报告": {
                "keywords": ["验收报告", "验收证明", "验收单", "验收书", "竣工验收"],
                "description": "项目验收证明",
            },
            "业绩证明函": {
                "keywords": ["业绩证明", "业绩证明函", "证明函", "业绩说明"],
                "description": "业主出具的业绩证明",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",
            "max_pages": 20,  # 业绩材料可能较多页
            "stop_conditions": ["新评分项标题"],
        },
        "examples": {
            "title_page": "业绩一览表/业绩证明文件目录",
            "material_pages": "后续的中标通知书、合同、验收报告等",
        }
    },

    # 设备类评分项
    "设备能力": {
        "category": "设备类",
        "description": "项目设备配置与投入证明",
        "title_keywords": [
            "设备能力", "设备配置", "设备投入", "设备清单",
            "无人机配置", "设备一览表", "主要设备", "设备情况"
        ],
        "material_types": {
            "发票": {
                "keywords": ["发票", "增值税发票", "购买发票", "购置发票", "普通发票"],
                "description": "设备购置发票",
                "multi_page": True,
            },
            "设备清单": {
                "keywords": ["设备清单", "设备表", "设备参数表", "设备一览表", "设备配置表"],
                "description": "设备基本信息表格",
            },
            "设备照片": {
                "keywords": ["设备照片", "无人机照片", "设备图片", "实物照片"],
                "description": "设备实物照片",
            },
            "租赁合同": {
                "keywords": ["租赁合同", "设备租赁", "租赁协议"],
                "description": "设备租赁证明（如适用）",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",
            "max_pages": 10,
            "stop_conditions": ["新评分项标题"],
        },
    },

    # 资质类评分项
    "企业资质": {
        "category": "资质类",
        "description": "企业资质证书与证明",
        "title_keywords": [
            "企业资质", "资质证书", "资质证明", "公司资质",
            "营业执照", "资质材料", "资质文件"
        ],
        "material_types": {
            "营业执照": {
                "keywords": ["营业执照", "工商执照", "企业法人营业执照"],
                "description": "企业营业执照",
            },
            "资质证书": {
                "keywords": ["资质证书", "行业资质", "专业资质", "等级证书"],
                "description": "行业资质证书",
            },
            "认证证书": {
                "keywords": ["认证证书", "ISO认证", "质量认证", "体系认证"],
                "description": "质量管理体系认证等",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",
            "max_pages": 5,
            "stop_conditions": ["新评分项标题"],
        },
    },

    # 技术方案类评分项
    "技术方案": {
        "category": "技术类",
        "description": "技术服务方案与技术响应",
        "title_keywords": [
            "技术方案", "技术服务方案", "实施方案", "作业方案",
            "技术响应", "技术部分", "技术偏离表"
        ],
        "material_types": {
            "技术偏离表": {
                "keywords": ["技术响应偏离表", "技术偏离表", "技术响应表"],
                "description": "技术要求响应表",
            },
            "作业计划": {
                "keywords": ["作业计划", "实施计划", "进度安排", "时间安排"],
                "description": "项目实施计划",
            },
            "安全管理": {
                "keywords": ["安全管理", "安全方案", "安全措施", "应急预案"],
                "description": "安全管理方案",
            },
            "质量保证": {
                "keywords": ["质量保证", "质量措施", "质量控制", "质量方案"],
                "description": "质量保证措施",
            },
        },
        "page_expansion_rule": {
            "direction": "section",  # 整个技术部分
            "max_pages": 20,
            "stop_conditions": ["商务部分开始", "其他部分开始"],
        },
    },

    # 商务方案类评分项
    "商务方案": {
        "category": "商务类",
        "description": "商务响应与商务条件",
        "title_keywords": [
            "商务方案", "商务响应", "商务部分", "商务偏离表",
            "商务条款", "商务条件"
        ],
        "material_types": {
            "商务偏离表": {
                "keywords": ["商务响应偏离表", "商务偏离表", "商务响应表"],
                "description": "商务条款响应表",
            },
            "服务承诺": {
                "keywords": ["服务承诺", "售后服务", "后续服务", "服务保障"],
                "description": "服务承诺文件",
            },
        },
        "page_expansion_rule": {
            "direction": "section",
            "max_pages": 15,
            "stop_conditions": ["技术部分开始"],
        },
    },

    # 价格类评分项（通常单页）
    "报价响应": {
        "category": "价格类",
        "description": "报价单与价格响应",
        "title_keywords": [
            "报价", "报价表", "报价单", "价格表", "报价响应",
            "报价文件", "分项报价"
        ],
        "material_types": {
            "报价表": {
                "keywords": ["报价表", "报价单", "价格表", "分项报价表"],
                "description": "报价表格",
            },
        },
        "page_expansion_rule": {
            "direction": "none",  # 通常不需要扩展
            "max_pages": 2,
        },
    },

    # 财务类评分项
    "财务状况": {
        "category": "财务类",
        "description": "企业财务状况证明",
        "title_keywords": [
            "财务状况", "财务报表", "财务证明", "财务报告",
            "资产负债", "审计报告"
        ],
        "material_types": {
            "财务报表": {
                "keywords": ["资产负债表", "利润表", "现金流量表", "财务报表"],
                "description": "财务报表",
                "multi_page": True,
            },
            "审计报告": {
                "keywords": ["审计报告", "财务审计", "会计师事务所"],
                "description": "财务审计报告",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",
            "max_pages": 10,
        },
    },

    # 信誉荣誉类评分项
    "信誉荣誉": {
        "category": "信誉类",
        "description": "企业信誉与荣誉证明",
        "title_keywords": [
            "信誉", "荣誉", "信誉状况", "荣誉证明", "荣誉证书",
            "信用证明", "获奖证书"
        ],
        "material_types": {
            "荣誉证书": {
                "keywords": ["荣誉证书", "获奖证书", "奖励证书", "表彰证书"],
                "description": "荣誉奖项证明",
            },
            "信用证明": {
                "keywords": ["信用证明", "信用等级", "信用证书", "诚信证明"],
                "description": "信用等级证明",
            },
        },
        "page_expansion_rule": {
            "direction": "forward",
            "max_pages": 5,
        },
    },
}


# ============== 知识库类 ==============

class ProcurementKnowledgeBase:
    """
    采购评分项知识库

    提供评分项类型识别、关键词匹配、证明材料检测等功能
    """

    def __init__(self, custom_config: Dict = None):
        """
        初始化知识库

        Args:
            custom_config: 自定义配置（可覆盖默认知识库）
        """
        self.knowledge = PROCUREMENT_REQUIREMENTS_KNOWLEDGE.copy()
        if custom_config:
            self.knowledge.update(custom_config)

        # 构建关键词索引（用于快速匹配）
        self._build_keyword_index()

    def _build_keyword_index(self):
        """构建关键词到评分项类型的反向索引"""
        self.keyword_index = {}
        for req_type, config in self.knowledge.items():
            for kw in config.get("title_keywords", []):
                self.keyword_index[kw] = req_type

    def parse_intent(self, query: str) -> Dict:
        """
        解析用户查询的评分项意图

        Args:
            query: 用户查询（如"人员配备"、"类似业绩"等）

        Returns:
            {
                "requirement_type": "人员配备",
                "category": "人员类",
                "title_keywords": [...],
                "material_types": {...},
                "page_expansion_rule": {...},
                "confidence": 0.9  # 匹配置信度
            }
        """
        # 直接匹配标题关键词
        best_match = None
        best_score = 0

        for req_type, config in self.knowledge.items():
            score = 0
            matched_keywords = []

            # 检查标题关键词匹配
            for kw in config.get("title_keywords", []):
                if kw in query:
                    score += 1
                    matched_keywords.append(kw)

            # 计算置信度
            if score > 0:
                confidence = min(score / len(config.get("title_keywords", [])), 1.0)
                if confidence > best_score:
                    best_score = confidence
                    best_match = {
                        "requirement_type": req_type,
                        "category": config.get("category"),
                        "description": config.get("description"),
                        "title_keywords": config.get("title_keywords", []),
                        "matched_keywords": matched_keywords,
                        "exclude_keywords": config.get("exclude_keywords", []),  # 添加排除词
                        "material_types": config.get("material_types", {}),
                        "page_expansion_rule": config.get("page_expansion_rule", {}),
                        "confidence": confidence,
                    }

        if best_match:
            return best_match

        # 没有匹配到，返回通用配置
        return {
            "requirement_type": "unknown",
            "category": "未知",
            "title_keywords": [query],  # 用查询词作为关键词
            "matched_keywords": [],
            "material_types": {},
            "page_expansion_rule": {"direction": "forward", "max_pages": 5},
            "confidence": 0,
            "suggestion": "未识别评分项类型，建议使用更具体的查询词",
        }

    def get_material_keywords(self, requirement_type: str) -> List[str]:
        """
        获取某评分项类型的所有证明材料关键词

        Args:
            requirement_type: 评分项类型

        Returns:
            证明材料关键词列表
        """
        config = self.knowledge.get(requirement_type, {})
        keywords = []
        for mat_type, mat_config in config.get("material_types", {}).items():
            keywords.extend(mat_config.get("keywords", []))
        return keywords

    def check_page_is_material(
        self,
        page_summary: str,
        requirement_type: str,
        material_type: str = None
    ) -> Dict:
        """
        检查页面是否为某评分项的证明材料

        Args:
            page_summary: 页面摘要
            requirement_type: 评分项类型
            material_type: 指定证明材料类型（可选）

        Returns:
            {
                "is_material": True/False,
                "material_type": "操作证",  # 检测到的材料类型
                "matched_keywords": ["操作手合格证"],
            }
        """
        config = self.knowledge.get(requirement_type, {})
        material_types = config.get("material_types", {})

        if material_type:
            # 只检查指定类型
            mat_config = material_types.get(material_type, {})
            keywords = mat_config.get("keywords", [])
            matched = [kw for kw in keywords if kw in page_summary]
            return {
                "is_material": len(matched) > 0,
                "material_type": material_type if matched else None,
                "matched_keywords": matched,
            }

        # 检查所有材料类型
        for mat_type, mat_config in material_types.items():
            keywords = mat_config.get("keywords", [])
            matched = [kw for kw in keywords if kw in page_summary]
            if matched:
                return {
                    "is_material": True,
                    "material_type": mat_type,
                    "matched_keywords": matched,
                    "description": mat_config.get("description"),
                }

        return {
            "is_material": False,
            "material_type": None,
            "matched_keywords": [],
        }

    def get_all_requirement_types(self) -> List[str]:
        """获取所有评分项类型"""
        return list(self.knowledge.keys())

    def get_category_requirements(self, category: str) -> List[str]:
        """获取某类别下的所有评分项"""
        return [
            req_type for req_type, config in self.knowledge.items()
            if config.get("category") == category
        ]


# ============== 辅助函数 ==============

def expand_page_range(
    title_pages: List[int],
    material_pages: List[int],
    merge_adjacent: bool = True,
    max_gap: int = 2
) -> List[str]:
    """
    将分散的页码合并为连续范围

    Args:
        title_pages: 标题页列表
        material_pages: 证明材料页列表
        merge_adjacent: 是否合并相邻范围
        max_gap: 最大允许间隔

    Returns:
        页码范围列表，如 ["85-89", "94"]
    """
    all_pages = sorted(set(title_pages + material_pages))

    if not all_pages:
        return []

    ranges = []
    start = all_pages[0]
    end = all_pages[0]

    for page in all_pages[1:]:
        if merge_adjacent and page <= end + max_gap + 1:
            # 连续或接近连续，扩展范围
            end = page
        else:
            # 间隔较大，新开范围
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = page
            end = page

    # 处理最后一个范围
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    return ranges


def format_retrieval_result(
    requirement_type: str,
    title_pages: List[int],
    material_pages: List[int],
    material_details: List[Dict] = None
) -> str:
    """
    格式化检索结果为用户友好文本

    Args:
        requirement_type: 评分项类型
        title_pages: 标题页
        material_pages: 证明材料页
        material_details: 证明材料详情

    Returns:
        格式化的文本报告
    """
    ranges = expand_page_range(title_pages, material_pages)

    lines = [
        f"【评分项】{requirement_type}",
        f"【定位页码】{', '.join(ranges)}",
        f"【标题页】{', '.join(map(str, title_pages)) or '无'}",
        f"【证明材料页】{', '.join(map(str, material_pages)) or '无'}",
    ]

    if material_details:
        lines.append("【证明材料详情】")
        for detail in material_details:
            lines.append(f"  - 第{detail['page']}页: {detail['material_type']} ({detail['matched_keywords']})")

    return "\n".join(lines)