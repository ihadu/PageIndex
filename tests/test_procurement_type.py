"""
采购类型分类功能单元测试

测试 ProcurementType 枚举、PROCUREMENT_TYPE_KNOWLEDGE 配置、
ProcurementKnowledgeBase 类型相关方法、API向后兼容性
"""

import pytest
from pageindex.procurement_knowledge import (
    ProcurementType,
    ProcurementKnowledgeBase,
    PROCUREMENT_TYPE_KNOWLEDGE,
    PROCUREMENT_REQUIREMENTS_KNOWLEDGE,
)


class TestProcurementTypeEnum:
    """采购类型枚举测试"""

    def test_type_enum_values(self):
        """测试枚举值"""
        assert ProcurementType.GOODS.value == "货物类"
        assert ProcurementType.SERVICES.value == "服务类"

    def test_type_enum_count(self):
        """测试枚举数量"""
        assert len(ProcurementType) == 2

    def test_type_enum_string_representation(self):
        """测试枚举字符串表示"""
        assert str(ProcurementType.GOODS) == "ProcurementType.GOODS"
        assert str(ProcurementType.SERVICES) == "ProcurementType.SERVICES"


class TestProcurementTypeKnowledge:
    """采购类型配置测试"""

    def test_type_config_exists(self):
        """测试类型配置存在"""
        assert ProcurementType.GOODS in PROCUREMENT_TYPE_KNOWLEDGE
        assert ProcurementType.SERVICES in PROCUREMENT_TYPE_KNOWLEDGE

    def test_goods_price_weight_range(self):
        """测试货物类价格权重范围"""
        config = PROCUREMENT_TYPE_KNOWLEDGE[ProcurementType.GOODS]
        assert "price_weight_range" in config
        assert config["price_weight_range"]["min"] == 30
        assert config["price_weight_range"]["max"] == 50

    def test_services_price_weight_range(self):
        """测试服务类价格权重范围"""
        config = PROCUREMENT_TYPE_KNOWLEDGE[ProcurementType.SERVICES]
        assert "price_weight_range" in config
        assert config["price_weight_range"]["min"] == 10
        assert config["price_weight_range"]["max"] == 30

    def test_goods_key_requirements(self):
        """测试货物类关键评分项"""
        config = PROCUREMENT_TYPE_KNOWLEDGE[ProcurementType.GOODS]
        assert "key_requirements" in config
        assert "设备能力" in config["key_requirements"]

    def test_services_key_requirements(self):
        """测试服务类关键评分项"""
        config = PROCUREMENT_TYPE_KNOWLEDGE[ProcurementType.SERVICES]
        assert "key_requirements" in config
        assert "人员配备" in config["key_requirements"]


class TestProcurementKnowledgeBaseTypeMethods:
    """知识库类型方法测试"""

    def setup_method(self):
        self.kb = ProcurementKnowledgeBase()

    def test_get_procurement_type_config_goods(self):
        """测试获取货物类配置"""
        config = self.kb.get_procurement_type_config(ProcurementType.GOODS)
        assert "price_weight_range" in config
        assert config["price_weight_range"]["min"] == 30
        assert config["price_weight_range"]["max"] == 50

    def test_get_procurement_type_config_services(self):
        """测试获取服务类配置"""
        config = self.kb.get_procurement_type_config(ProcurementType.SERVICES)
        assert "price_weight_range" in config
        assert config["price_weight_range"]["min"] == 10
        assert config["price_weight_range"]["max"] == 30

    def test_get_requirements_for_type_goods(self):
        """测试获取货物类适用评分项"""
        goods_reqs = self.kb.get_requirements_for_type(ProcurementType.GOODS)
        assert "设备能力" in goods_reqs
        # 人员配备是服务类专用，不应在货物类出现
        assert "人员配备" not in goods_reqs

    def test_get_requirements_for_type_services(self):
        """测试获取服务类适用评分项"""
        services_reqs = self.kb.get_requirements_for_type(ProcurementType.SERVICES)
        assert "人员配备" in services_reqs
        # 设备能力是货物类专用，不应在服务类出现
        assert "设备能力" not in services_reqs

    def test_get_all_procurement_types(self):
        """测试获取所有类型"""
        types = self.kb.get_all_procurement_types()
        assert ProcurementType.GOODS in types
        assert ProcurementType.SERVICES in types
        assert len(types) == 2

    def test_type_config_loaded_in_init(self):
        """测试类型配置在初始化时加载"""
        assert self.kb.type_config == PROCUREMENT_TYPE_KNOWLEDGE


class TestRequirementTypesField:
    """评分项 procurement_types 字段测试"""

    def test_personnel_services_only(self):
        """测试人员配备仅适用于服务类"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["人员配备"]
        assert "procurement_types" in config
        assert ProcurementType.SERVICES in config["procurement_types"]
        assert ProcurementType.GOODS not in config["procurement_types"]

    def test_equipment_goods_only(self):
        """测试设备能力仅适用于货物类"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["设备能力"]
        assert "procurement_types" in config
        assert ProcurementType.GOODS in config["procurement_types"]
        assert ProcurementType.SERVICES not in config["procurement_types"]

    def test_similar_performance_both(self):
        """测试类似业绩适用于两种类型"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["类似业绩"]
        assert "procurement_types" in config
        assert ProcurementType.GOODS in config["procurement_types"]
        assert ProcurementType.SERVICES in config["procurement_types"]

    def test_technical_plan_services_only(self):
        """测试技术方案仅适用于服务类"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["技术方案"]
        assert "procurement_types" in config
        assert ProcurementType.SERVICES in config["procurement_types"]

    def test_all_requirements_have_procurement_types_field(self):
        """测试所有评分项都有 procurement_types 字段"""
        for req_type, config in PROCUREMENT_REQUIREMENTS_KNOWLEDGE.items():
            assert "procurement_types" in config, f"{req_type} 缺少 procurement_types 字段"


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def setup_method(self):
        self.kb = ProcurementKnowledgeBase()

    def test_parse_intent_default_param(self):
        """测试默认参数行为不变"""
        # 不传 procurement_type，行为应与现有完全一致
        result = self.kb.parse_intent("人员配备")
        assert result["requirement_type"] == "人员配备"
        assert result["category"] == "人员类"

    def test_parse_intent_with_services_type(self):
        """测试服务类类型过滤"""
        result = self.kb.parse_intent("人员配备", procurement_type=ProcurementType.SERVICES)
        assert result["requirement_type"] == "人员配备"

    def test_parse_intent_goods_type_filters_services_item(self):
        """测试货物类类型过滤排除服务类评分项"""
        # 人员配备是服务类专用，货物类查询应返回 unknown
        result = self.kb.parse_intent("人员配备", procurement_type=ProcurementType.GOODS)
        # 由于人员配备不适用于货物类，应该匹配不到
        assert result["requirement_type"] == "unknown"

    def test_get_all_requirement_types_default(self):
        """测试默认返回全部"""
        types = self.kb.get_all_requirement_types()
        assert len(types) >= 9  # 现有9种评分项
        assert "人员配备" in types
        assert "设备能力" in types

    def test_get_all_requirement_types_goods_filter(self):
        """测试货物类过滤"""
        types = self.kb.get_all_requirement_types(ProcurementType.GOODS)
        # 设备能力应在货物类列表中
        assert "设备能力" in types
        # 人员配备是服务类专用，不应在货物类列表中
        assert "人员配备" not in types

    def test_get_all_requirement_types_services_filter(self):
        """测试服务类过滤"""
        types = self.kb.get_all_requirement_types(ProcurementType.SERVICES)
        # 人员配备应在服务类列表中
        assert "人员配备" in types
        # 设备能力是货物类专用，不应在服务类列表中
        assert "设备能力" not in types

    def test_get_material_keywords_unchanged(self):
        """测试 get_material_keywords 方法不变"""
        result = self.kb.get_material_keywords("人员配备")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_check_page_is_material_unchanged(self):
        """测试 check_page_is_material 方法不变"""
        result = self.kb.check_page_is_material("操作手合格证", "人员配备")
        assert result["is_material"] == True
        assert result["material_type"] == "操作证"

    def test_get_category_requirements_unchanged(self):
        """测试 get_category_requirements 方法不变"""
        result = self.kb.get_category_requirements("人员类")
        assert "人员配备" in result


class TestTypeFilteringIntegration:
    """类型过滤集成测试"""

    def setup_method(self):
        self.kb = ProcurementKnowledgeBase()

    def test_goods_type_only_searches_goods_requirements(self):
        """测试货物类仅搜索货物类评分项"""
        # 设备能力是货物类专用
        result = self.kb.parse_intent("设备能力", procurement_type=ProcurementType.GOODS)
        assert result["requirement_type"] == "设备能力"
        assert ProcurementType.GOODS in result["procurement_types"]

    def test_services_type_only_searches_services_requirements(self):
        """测试服务类仅搜索服务类评分项"""
        # 技术方案是服务类专用
        result = self.kb.parse_intent("技术方案", procurement_type=ProcurementType.SERVICES)
        assert result["requirement_type"] == "技术方案"
        assert ProcurementType.SERVICES in result["procurement_types"]

    def test_common_requirements_match_both_types(self):
        """测试通用评分项匹配两种类型"""
        # 类似业绩是通用的
        goods_result = self.kb.parse_intent("类似业绩", procurement_type=ProcurementType.GOODS)
        services_result = self.kb.parse_intent("类似业绩", procurement_type=ProcurementType.SERVICES)

        assert goods_result["requirement_type"] == "类似业绩"
        assert services_result["requirement_type"] == "类似业绩"


class TestWeightRangeField:
    """评分项 weight_range 字段测试"""

    def test_personnel_services_weight_range(self):
        """测试人员配备服务类权重范围"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["人员配备"]
        weight_range = config.get("weight_range", {})
        services_weight = weight_range.get(ProcurementType.SERVICES)
        assert services_weight is not None
        assert services_weight["min"] == 10
        assert services_weight["max"] == 25

    def test_personnel_goods_weight_none(self):
        """测试人员配备货物类权重为None"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["人员配备"]
        weight_range = config.get("weight_range", {})
        goods_weight = weight_range.get(ProcurementType.GOODS)
        assert goods_weight is None

    def test_price_goods_weight_high(self):
        """测试报价响应货物类权重高"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["报价响应"]
        weight_range = config.get("weight_range", {})
        goods_weight = weight_range.get(ProcurementType.GOODS)
        assert goods_weight["min"] == 30
        assert goods_weight["max"] == 50

    def test_price_services_weight_low(self):
        """测试报价响应服务类权重低"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["报价响应"]
        weight_range = config.get("weight_range", {})
        services_weight = weight_range.get(ProcurementType.SERVICES)
        assert services_weight["min"] == 10
        assert services_weight["max"] == 30

    def test_equipment_goods_weight_range(self):
        """测试设备能力货物类权重范围"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["设备能力"]
        weight_range = config.get("weight_range", {})
        goods_weight = weight_range.get(ProcurementType.GOODS)
        assert goods_weight["min"] == 15
        assert goods_weight["max"] == 25

    def test_all_requirements_have_weight_range_field(self):
        """测试所有评分项都有 weight_range 字段"""
        for req_type, config in PROCUREMENT_REQUIREMENTS_KNOWLEDGE.items():
            assert "weight_range" in config, f"{req_type} 缺少 weight_range 字段"


class TestWeightMethods:
    """权重方法测试"""

    def setup_method(self):
        self.kb = ProcurementKnowledgeBase()

    def test_get_weight_info_services(self):
        """测试获取服务类权重信息"""
        weight = self.kb.get_weight_info("人员配备", ProcurementType.SERVICES)
        assert weight is not None
        assert weight["min"] == 10
        assert weight["max"] == 25

    def test_get_weight_info_goods_none(self):
        """测试货物类不适用评分项返回None"""
        weight = self.kb.get_weight_info("人员配备", ProcurementType.GOODS)
        assert weight is None

    def test_get_all_weights_for_type_goods(self):
        """测试获取货物类所有权重"""
        weights = self.kb.get_all_weights_for_type(ProcurementType.GOODS)
        # 设备能力应有权重
        assert weights["设备能力"] is not None
        # 人员配备应为None
        assert weights["人员配备"] is None

    def test_get_all_weights_for_type_services(self):
        """测试获取服务类所有权重"""
        weights = self.kb.get_all_weights_for_type(ProcurementType.SERVICES)
        # 人员配备应有权重
        assert weights["人员配备"] is not None
        # 设备能力应为None
        assert weights["设备能力"] is None

    def test_validate_weights_valid_config(self):
        """测试有效权重配置验证"""
        # 构造一个有效的服务类权重配置
        config = {
            "报价响应": 20,
            "技术方案": 30,
            "人员配备": 15,
            "类似业绩": 15,
            "企业资质": 10,
            "信誉荣誉": 10,
        }
        result = self.kb.validate_weights(ProcurementType.SERVICES, config)
        assert result["is_valid"] == True
        assert result["total"] == 100

    def test_validate_weights_invalid_total(self):
        """测试权重总和不为100"""
        config = {
            "报价响应": 20,
            "技术方案": 30,
        }
        result = self.kb.validate_weights(ProcurementType.SERVICES, config)
        assert result["is_valid"] == False
        assert "权重总和" in str(result["issues"])

    def test_validate_weights_out_of_range(self):
        """测试权重超出范围"""
        # 报价响应服务类最大30分
        config = {
            "报价响应": 50,  # 超出最大值
            "技术方案": 30,
            "人员配备": 20,
        }
        result = self.kb.validate_weights(ProcurementType.SERVICES, config)
        assert result["is_valid"] == False
        assert any("高于最大值" in issue for issue in result["issues"])

    def test_validate_weights_inapplicable_requirement(self):
        """测试不适用评分项"""
        # 设备能力不适用于服务类
        config = {
            "设备能力": 10,  # 不适用
            "报价响应": 20,
            "技术方案": 30,
            "人员配备": 20,
            "类似业绩": 20,
        }
        result = self.kb.validate_weights(ProcurementType.SERVICES, config)
        assert result["is_valid"] == False
        assert any("不适用于" in issue for issue in result["issues"])


class TestPolicyRequirement:
    """政策性评分项测试"""

    def test_sme_declaration_exists(self):
        """测试中小企业声明函存在"""
        assert "中小企业声明函" in PROCUREMENT_REQUIREMENTS_KNOWLEDGE

    def test_sme_declaration_category(self):
        """测试中小企业声明函类别"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        assert config["category"] == "政策类"

    def test_sme_declaration_is_policy(self):
        """测试中小企业声明函政策标记"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        assert config.get("is_policy_requirement") == True

    def test_sme_declaration_policy_type(self):
        """测试中小企业声明函政策类型"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        assert config.get("policy_type") == "中小企业扶持"

    def test_sme_declaration_policy_reference(self):
        """测试中小企业声明函政策依据"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        assert config.get("policy_reference") == "财库〔2020〕46号"

    def test_sme_declaration_applicable_to_both_types(self):
        """测试中小企业声明函适用于两种类型"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        applicable = config.get("procurement_types", [])
        assert ProcurementType.GOODS in applicable
        assert ProcurementType.SERVICES in applicable

    def test_sme_declaration_title_keywords(self):
        """测试中小企业声明函标题关键词"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        keywords = config.get("title_keywords", [])
        assert "中小企业声明函" in keywords
        assert "小微企业声明" in keywords

    def test_sme_declaration_single_page(self):
        """测试中小企业声明函单页结构"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        expansion = config.get("page_expansion_rule", {})
        assert expansion.get("direction") == "none"
        assert expansion.get("max_pages") == 1

    def test_sme_declaration_price_deduction_range(self):
        """测试中小企业声明函价格扣除范围"""
        config = PROCUREMENT_REQUIREMENTS_KNOWLEDGE["中小企业声明函"]
        deduction = config.get("price_deduction_range", {})
        assert deduction["min"] == 6
        assert deduction["max"] == 10


class TestPolicyMethods:
    """政策性评分项方法测试"""

    def setup_method(self):
        self.kb = ProcurementKnowledgeBase()

    def test_get_policy_requirements(self):
        """测试获取政策性评分项列表"""
        policy_reqs = self.kb.get_policy_requirements()
        assert "中小企业声明函" in policy_reqs

    def test_get_policy_requirements_goods_filter(self):
        """测试货物类政策性评分项过滤"""
        policy_reqs = self.kb.get_policy_requirements(ProcurementType.GOODS)
        assert "中小企业声明函" in policy_reqs

    def test_get_policy_requirements_services_filter(self):
        """测试服务类政策性评分项过滤"""
        policy_reqs = self.kb.get_policy_requirements(ProcurementType.SERVICES)
        assert "中小企业声明函" in policy_reqs

    def test_get_policy_info(self):
        """测试获取政策信息"""
        info = self.kb.get_policy_info("中小企业声明函")
        assert info is not None
        assert info["policy_type"] == "中小企业扶持"
        assert info["policy_reference"] == "财库〔2020〕46号"

    def test_get_policy_info_non_policy(self):
        """测试非政策性评分项返回None"""
        info = self.kb.get_policy_info("人员配备")
        assert info is None

    def test_check_policy_compliance(self):
        """测试政策合规检查"""
        result = self.kb.check_policy_compliance("中小企业声明函")
        assert result["is_policy"] == True
        assert result["policy_type"] == "中小企业扶持"
        assert len(result["compliance_notes"]) > 0

    def test_check_policy_compliance_non_policy(self):
        """测试非政策性评分项合规检查"""
        result = self.kb.check_policy_compliance("人员配备")
        assert result["is_policy"] == False
        assert result["compliance_notes"] == []

    def test_parse_intent_sme_declaration(self):
        """测试中小企业声明函意图解析"""
        result = self.kb.parse_intent("中小企业声明函")
        assert result["requirement_type"] == "中小企业声明函"
        assert result["category"] == "政策类"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])