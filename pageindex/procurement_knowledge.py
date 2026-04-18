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
from enum import Enum
import re


# ============== 采购类型枚举 ==============

class ProcurementType(str, Enum):
    """
    采购类型枚举

    财政部87号令规定货物类和服务类评分权重不同：
    - 货物类：价格权重30-50%，设备能力是关键评分项
    - 服务类：价格权重10-30%，人员配备是关键评分项
    """
    GOODS = "货物类"
    SERVICES = "服务类"


# ============== 采购类型配置 ==============

PROCUREMENT_TYPE_KNOWLEDGE = {
    ProcurementType.GOODS: {
        "description": "货物采购项目（设备、物资、产品等）",
        "price_weight_range": {"min": 30, "max": 50},
        "key_requirements": ["设备能力", "企业资质", "报价响应"],
        "typical_materials": ["发票", "质量证明", "设备清单"],
        "evaluation_focus": "性价比、质量证明、设备配置",
    },
    ProcurementType.SERVICES: {
        "description": "服务采购项目（技术服务、咨询服务等）",
        "price_weight_range": {"min": 10, "max": 30},
        "key_requirements": ["人员配备", "类似业绩", "技术方案"],
        "typical_materials": ["合同", "业绩证明", "人员证书"],
        "evaluation_focus": "人员资质、业绩经验、方案质量",
    },
}


# ============== 采购评分项标准知识库 ==============

PROCUREMENT_REQUIREMENTS_KNOWLEDGE = {
    # 人员类评分项（服务类专用）
    "人员配备": {
        "category": "人员类",
        "procurement_types": [ProcurementType.SERVICES],  # 服务类专用
        "weight_range": {
            ProcurementType.GOODS: None,  # 货物类不适用
            ProcurementType.SERVICES: {"min": 10, "max": 25},  # 服务类: 10-25分
        },
        "description": "项目人员配置与资质证明",
        "title_keywords": [
            "人员配备", "人员配置", "作业人员", "人员名单",
            "人员构成", "人员安排", "人员组织", "技术人员",
            "飞防作业队", "飞手配置", "操作人员"
        ],
        # v1.2新增：证明材料关键词也可触发标题页定位（权重更高）
        "material_as_title_keywords": [
            "操作手合格证", "植保无人机操作证", "飞手证"
        ],
        # v1.2新增：人员信息特征检测（更本质的判断方式）
        # 用于识别人员证明材料页面（包含多人个人信息）
        "person_info_pattern": {
            "core_fields": ["姓名", "性别", "出生日期"],  # 核心字段（必须包含）
            "optional_fields": ["年龄", "身份证", "证书编号", "发证日期", "有效期"],  # 可选字段
            "multi_person_indicators": ["位人员", "张证书", "人员名单", "共"],  # 多人列表标志
            "min_field_count": 2,  # 至少匹配2个核心字段
        },
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
            "direction": "bidirectional",  # v1.2：人员配备证明材料可能在标题页之前
            "max_pages": 15,  # 前后各扩展15页
            "backward_pages": 10,  # 向前扩展10页
            "stop_conditions": ["新章节标题", "下一个评分项"],
        },
        "examples": {
            "title_page": "人员配备方案/人员配置表",
            "material_pages": "后续连续的操作证、培训证明等证书页面",
        }
    },

    # 业绩类评分项（通用）
    "类似业绩": {
        "category": "业绩类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 5, "max": 10},  # 货物类: 5-10分
            ProcurementType.SERVICES: {"min": 10, "max": 20},  # 服务类: 10-20分
        },
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
                "keywords": [
                    "中标通知书", "成交通知书", "中标公告", "成交公告", "中标结果",
                    # v1.2新增：关键词变体
                    "中标（成交）通知书", "中标(成交)通知书", "中标成交通知书",
                ],
                "description": "项目中标/成交证明文件",
            },
            "合同": {
                "keywords": [
                    # 强关键词：明确标识合同首页
                    "政府采购合同", "服务合同", "采购合同", "合同书", "协议书",
                    "合同条款", "合同附件",
                    # v1.2新增：补助协议等变体
                    "补助协议", "采购协议", "服务协议",
                ],
                # 弱关键词：用于连续性追踪，不单独触发检测
                "weak_keywords": [
                    "条款页", "合同约定", "违约责任", "付款方式",
                    "结算方式", "双方权利义务", "合同编号", "合同签署",
                    "合同生效", "权利义务", "知识产权", "质量保证"
                ],
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
            "max_pages": 50,  # v1.2：业绩材料可能超过20页，放宽限制
            "stop_conditions": ["新评分项标题"],
        },
        "examples": {
            "title_page": "业绩一览表/业绩证明文件目录",
            "material_pages": "后续的中标通知书、合同、验收报告等",
        }
    },

    # 设备类评分项（货物类专用）
    "设备能力": {
        "category": "设备类",
        "procurement_types": [ProcurementType.GOODS],  # 货物类专用
        "weight_range": {
            ProcurementType.GOODS: {"min": 15, "max": 25},  # 货物类: 15-25分（技术指标的一部分）
            ProcurementType.SERVICES: None,  # 服务类不适用
        },
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

    # 资质类评分项（通用）
    "企业资质": {
        "category": "资质类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 5, "max": 10},  # 货物类: 5-10分
            ProcurementType.SERVICES: {"min": 5, "max": 15},  # 服务类: 5-15分
        },
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

    # 技术方案类评分项（服务类专用）
    "技术方案": {
        "category": "技术类",
        "procurement_types": [ProcurementType.SERVICES],  # 服务类专用
        "weight_range": {
            ProcurementType.GOODS: None,  # 货物类不适用
            ProcurementType.SERVICES: {"min": 20, "max": 40},  # 服务类: 20-40分
        },
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

    # 商务方案类评分项（通用）
    "商务方案": {
        "category": "商务类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 5, "max": 15},  # 货物类: 5-15分（售后服务）
            ProcurementType.SERVICES: {"min": 5, "max": 10},  # 服务类: 5-10分
        },
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

    # 价格类评分项（通用，但权重差异显著）
    "报价响应": {
        "category": "价格类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用（权重差异）
        "weight_range": {
            ProcurementType.GOODS: {"min": 30, "max": 50},  # 货物类: 30-50分（87号令规定）
            ProcurementType.SERVICES: {"min": 10, "max": 30},  # 服务类: 10-30分（87号令规定）
        },
        "description": "报价单与价格响应",
        "title_keywords": [
            # v1.2：移除通用词"报价"，避免误匹配合同条款页中的"报价表"
            "报价表", "报价单", "价格表", "报价响应",
            "报价文件", "分项报价", "报价一览表"
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

    # 财务类评分项（通用）
    "财务状况": {
        "category": "财务类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 5, "max": 10},  # 货物类: 5-10分
            ProcurementType.SERVICES: {"min": 5, "max": 10},  # 服务类: 5-10分
        },
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

    # 信誉荣誉类评分项（通用）
    "信誉荣誉": {
        "category": "信誉类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 3, "max": 8},  # 货物类: 3-8分（可选）
            ProcurementType.SERVICES: {"min": 5, "max": 10},  # 服务类: 5-10分
        },
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

    # ============== 政策性评分项 ==============

    # 中小企业声明函（财库〔2020〕46号）
    "中小企业声明函": {
        "category": "政策类",
        "procurement_types": [ProcurementType.GOODS, ProcurementType.SERVICES],  # 通用
        "weight_range": {
            ProcurementType.GOODS: {"min": 3, "max": 5},  # 货物类: 3-5分（价格扣除6-10%转化）
            ProcurementType.SERVICES: {"min": 3, "max": 5},  # 服务类: 3-5分
        },
        "description": "中小企业身份声明函，享受政策优惠加分",
        "title_keywords": [
            "中小企业声明函", "中小企业声明", "小微企业声明",
            "中型企业声明", "企业类型声明", "中小企业认定"
        ],
        "material_types": {
            "声明函": {
                "keywords": ["从业人员", "营业收入", "资产总额", "所属行业", "企业规模"],
                "description": "企业规模声明内容",
                "is_policy_doc": True,  # 政策性文件标记
                "single_page": True,  # 单页结构
            },
            "营业执照": {
                "keywords": ["营业执照", "工商执照", "企业法人营业执照"],
                "description": "佐证企业类型的营业执照",
            },
        },
        "page_expansion_rule": {
            "direction": "none",  # 单页，不扩展
            "max_pages": 1,
        },
        "is_policy_requirement": True,  # 政策性评分项标记
        "policy_type": "中小企业扶持",  # 政策类型
        "policy_reference": "财库〔2020〕46号",  # 政策依据
        "price_deduction_range": {"min": 6, "max": 10},  # 价格扣除比例（%）
        "examples": {
            "title_page": "中小企业声明函",
            "material_pages": "单页声明，无需扩展",
        }
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

        # 加载类型配置
        self.type_config = PROCUREMENT_TYPE_KNOWLEDGE

        # 构建关键词索引（用于快速匹配）
        self._build_keyword_index()

    def _build_keyword_index(self):
        """构建关键词到评分项类型的反向索引"""
        self.keyword_index = {}
        for req_type, config in self.knowledge.items():
            for kw in config.get("title_keywords", []):
                self.keyword_index[kw] = req_type

    def parse_intent(self, query: str, procurement_type: ProcurementType = None) -> Dict:
        """
        解析用户查询的评分项意图

        Args:
            query: 用户查询（如"人员配备"、"类似业绩"等）
            procurement_type: 采购类型过滤（可选）
                             None = 不过滤（默认，保持向后兼容）
                             ProcurementType.GOODS = 仅返回货物类评分项
                             ProcurementType.SERVICES = 仅返回服务类评分项

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

            # 类型过滤：检查评分项是否适用于指定类型
            if procurement_type:
                applicable_types = config.get("procurement_types", [])
                # 如果评分项有类型限制，检查是否匹配
                if applicable_types and procurement_type not in applicable_types:
                    continue  # 跳过不匹配的评分项

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
                        "procurement_types": config.get("procurement_types", []),  # 新增
                        "title_keywords": config.get("title_keywords", []),
                        "material_as_title_keywords": config.get("material_as_title_keywords", []),  # v1.2新增
                        "person_info_pattern": config.get("person_info_pattern", {}),  # v1.2新增：人员信息特征检测
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
            "procurement_types": [],
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

    def get_all_requirement_types(self, procurement_type: ProcurementType = None) -> List[str]:
        """
        获取所有评分项类型名称

        Args:
            procurement_type: 采购类型过滤（可选）
                             None = 返回全部（默认，保持兼容）

        Returns:
            List[str]: 评分项类型名称列表
        """
        all_types = list(self.knowledge.keys())

        if procurement_type:
            # 过滤：仅返回该类型适用的评分项
            filtered = []
            for req_type in all_types:
                requirement = self.knowledge.get(req_type, {})
                applicable_types = requirement.get("procurement_types", [])
                # 无类型限制或匹配指定类型
                if not applicable_types or procurement_type in applicable_types:
                    filtered.append(req_type)
            return filtered

        return all_types

    def get_all_title_keywords(self, exclude_type: str = None) -> List[str]:
        """
        获取所有评分项的标题关键词（用于停止条件检测）

        Args:
            exclude_type: 要排除的评分项类型（当前正在检索的类型）

        Returns:
            List[str]: 所有标题关键词列表
        """
        all_keywords = []
        for req_type, config in self.knowledge.items():
            if req_type == exclude_type:
                continue  # 排除当前评分项
            title_keywords = config.get("title_keywords", [])
            all_keywords.extend(title_keywords)
        return all_keywords

    def get_category_requirements(self, category: str) -> List[str]:
        """获取某类别下的所有评分项"""
        return [
            req_type for req_type, config in self.knowledge.items()
            if config.get("category") == category
        ]

    def get_procurement_type_config(self, procurement_type: ProcurementType) -> Dict:
        """
        获取采购类型配置信息

        Args:
            procurement_type: 采购类型枚举值

        Returns:
            Dict: 类型配置（description, price_weight_range, key_requirements等）
        """
        return PROCUREMENT_TYPE_KNOWLEDGE.get(procurement_type, {})

    def get_requirements_for_type(self, procurement_type: ProcurementType) -> List[str]:
        """
        获取指定采购类型适用的评分项列表

        Args:
            procurement_type: 采购类型枚举值

        Returns:
            List[str]: 该类型适用的评分项名称列表
        """
        config = self.get_procurement_type_config(procurement_type)
        return config.get("key_requirements", [])

    def get_all_procurement_types(self) -> List[ProcurementType]:
        """
        获取所有采购类型枚举值

        Returns:
            List[ProcurementType]: 所有采购类型列表
        """
        return list(ProcurementType)

    def get_weight_info(self, requirement_type: str, procurement_type: ProcurementType) -> Optional[Dict]:
        """
        获取评分项在指定采购类型下的权重范围

        Args:
            requirement_type: 评分项类型名称
            procurement_type: 采购类型枚举值

        Returns:
            Dict: 权重范围 {"min": 10, "max": 25} 或 None（不适用）
        """
        config = self.knowledge.get(requirement_type, {})
        weight_range = config.get("weight_range", {})
        return weight_range.get(procurement_type)

    def get_all_weights_for_type(self, procurement_type: ProcurementType) -> Dict[str, Optional[Dict]]:
        """
        获取指定采购类型下所有评分项的权重范围

        Args:
            procurement_type: 采购类型枚举值

        Returns:
            Dict: {评分项名称: {"min": x, "max": y} 或 None}
        """
        weights = {}
        for req_type, config in self.knowledge.items():
            weight_range = config.get("weight_range", {})
            weights[req_type] = weight_range.get(procurement_type)
        return weights

    def validate_weights(self, procurement_type: ProcurementType, weight_config: Dict[str, int]) -> Dict:
        """
        验证权重配置是否合规

        Args:
            procurement_type: 采购类型枚举值
            weight_config: {评分项名称: 分值} 配置

        Returns:
            Dict: {
                "is_valid": True/False,
                "total": 总分值,
                "issues": ["问题列表"],
                "warnings": ["警告列表"]
            }
        """
        issues = []
        warnings = []
        total = 0

        for req_type, weight in weight_config.items():
            weight_range = self.get_weight_info(req_type, procurement_type)

            if weight_range is None:
                # 评分项不适用于该类型
                issues.append(f"{req_type} 不适用于{procurement_type.value}")
                continue

            total += weight

            if weight_range:
                # 有权重范围限制
                if weight < weight_range["min"]:
                    issues.append(f"{req_type} 权重{weight}低于最小值{weight_range['min']}")
                elif weight > weight_range["max"]:
                    issues.append(f"{req_type} 权重{weight}高于最大值{weight_range['max']}")
                elif weight == weight_range["max"]:
                    warnings.append(f"{req_type} 权重达到上限{weight_range['max']}")

        # 总分应为100分
        if total != 100:
            issues.append(f"权重总和{total}不等于100分")

        return {
            "is_valid": len(issues) == 0,
            "total": total,
            "issues": issues,
            "warnings": warnings,
        }

    def get_policy_requirements(self, procurement_type: ProcurementType = None) -> List[str]:
        """
        获取政策性评分项列表

        Args:
            procurement_type: 采购类型过滤（可选）
                             None = 返回全部政策性评分项

        Returns:
            List[str]: 政策性评分项名称列表
        """
        policy_reqs = []
        for req_type, config in self.knowledge.items():
            if config.get("is_policy_requirement"):
                if procurement_type:
                    applicable_types = config.get("procurement_types", [])
                    if applicable_types and procurement_type not in applicable_types:
                        continue
                policy_reqs.append(req_type)
        return policy_reqs

    def get_policy_info(self, requirement_type: str) -> Optional[Dict]:
        """
        获取政策性评分项详细信息

        Args:
            requirement_type: 评分项类型名称

        Returns:
            Dict: 政策信息（policy_type, policy_reference, price_deduction_range等）
                  或 None（非政策性评分项）
        """
        config = self.knowledge.get(requirement_type, {})
        if not config.get("is_policy_requirement"):
            return None

        return {
            "policy_type": config.get("policy_type"),
            "policy_reference": config.get("policy_reference"),
            "price_deduction_range": config.get("price_deduction_range"),
            "is_policy_doc": True,
        }

    def check_policy_compliance(self, requirement_type: str) -> Dict:
        """
        检查政策性评分项合规性

        Args:
            requirement_type: 评分项类型名称

        Returns:
            Dict: {
                "is_policy": True/False,
                "policy_type": "中小企业扶持",
                "compliance_notes": ["注意事项列表"]
            }
        """
        config = self.knowledge.get(requirement_type, {})
        is_policy = config.get("is_policy_requirement", False)

        if not is_policy:
            return {
                "is_policy": False,
                "policy_type": None,
                "compliance_notes": [],
            }

        notes = []
        policy_type = config.get("policy_type")

        # 根据政策类型添加合规提示
        if policy_type == "中小企业扶持":
            notes.extend([
                "小微企业享受6%-10%价格扣除优惠",
                "需核实从业人员、营业收入、资产总额是否符合小微企业标准",
                "联合体投标需提供联合体协议",
            ])

        return {
            "is_policy": True,
            "policy_type": policy_type,
            "policy_reference": config.get("policy_reference"),
            "price_deduction_range": config.get("price_deduction_range"),
            "compliance_notes": notes,
        }


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