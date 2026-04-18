# PageIndex 采购评分项知识库系统

## What This Is

PageIndex 是一个**向量无关、基于推理的 RAG 系统**，专门用于政府采购响应文件的智能检索。系统通过构建层级树结构索引，模拟人类专家导航和提取知识的方式，解决评审专家需要在有限时间内快速定位评分项页码的核心痛点。

当前版本聚焦**货物和服务类采购**，采用综合评分法，支持扫描件 PDF 检索。

## Core Value

**让评审专家快速定位评分项页码**——这是政府采购评审效率提升的关键需求。

## Current Milestone: v1.3 规划中

**Goal:** 待规划（可能的候选：绿色产品认证、地区知识库、有效性检测）

**预估时间:** TBD

## Requirements

### Validated

<!-- 已验证的功能 -->

**v1.0 基础版本：**
- ✓ **基础树结构索引** — 从 PDF 生成层级树结构 — v1.0
- ✓ **视觉检索（VisionPageIndex）** — 直接处理 PDF 页面图片 — v1.0
- ✓ **多轮扩展检索** — 标题页 + 证明材料页自动合并 — v1.0
- ✓ **采购评分项知识库** — 9种评分项映射 — v1.0
- ✓ **关键词排除机制** — 过滤偏离表等干扰页面 — v1.0
- ✓ **OpenAI Agents SDK 集成** — 支持 Chat Completions API — v1.0
- ✓ **LiteLLM 兼容** — 支持阿里云 DashScope — v1.0
- ✓ **工作区持久化** — 索引缓存避免重复生成 — v1.0
- ✓ **知识库构建工具** — TenderParser、KeywordDiscovery 等 — v1.0

**v1.1 政府采购增强：**
- ✓ **TYPE-01**: 采购类型分类（货物类/服务类） — v1.1
- ✓ **TYPE-02**: 评分项权重差异化配置（weight_range） — v1.1
- ✓ **POLICY-01**: 中小企业声明函识别 — v1.1
- ✓ **COMPAT-01**: API 向后兼容 — v1.1
- ✓ **INT-01**: VisionPageIndex 类型参数 — v1.1

**v1.2 证明材料页漏检修复：**
- ✓ **连续性追踪** — `_should_continue_material()` 追踪多页证明材料 — v1.2
- ✓ **关键词分层** — 强关键词单独触发 + 弱关键词追踪 — v1.2
- ✓ **停止条件检测** — 遇到新评分项标题自动停止 — v1.2
- ✓ **双向搜索** — bidirectional 模式支持向前搜索 — v1.2
- ✓ **人员信息特征检测** — person_info_pattern 检测多人列表 — v1.2
- ✓ **扩展范围增大** — max_pages 从 20 增加到 50 — v1.2

### Active

<!-- v1.3 里程碑候选 -->

- [ ] **POLICY-02**: 绿色产品认证（需品目清单数据库）
- [ ] **REGION-01**: 地区知识库差异化（各省采购规则）
- [ ] **VALID-01**: 证明材料有效性检测（证书有效期、公章）

### Out of Scope

<!-- v1.1 明确排除 -->

- **工程类采购** — 不属于政府采购范围（适用招标投标法）
- **地区知识库** — 推迟到下一里程碑
- **有效性检测** — 推迟到下一里程碑
- **国际采购** — 仅支持中文政府采购文件
- **企业自主采购** — 非政府采购规则
- **评分结果自动计算** — 仅定位，不评分
- **证明材料合规性判定** — 需人工复核有效性
- **询价/竞争性谈判评审** — 仅支持综合评分法

## Context

### 政府采购背景

中国政府采购法律体系以《政府采购法》为核心，财政部87号令规定评分因素包括：价格、技术、商务、业绩、资信等。

**采购类型分类：**
| 类型 | 价格权重 | 关键评分项 |
|------|----------|-----------|
| 货物 | 30-50% | 设备发票、质量证明 |
| 服务 | 10-30% | 人员、业绩、技术方案 |

**当前系统评分：5.8/10**（政府采购场景需针对性增强）

### 技术环境

- 纯 Python 实现，无向量数据库依赖
- LiteLLM 支持多模型（OpenAI、阿里云 DashScope）
- OpenAI Agents SDK Agent 集成
- 工作区持久化缓存

## Constraints

- **采购类型限制**：仅覆盖货物和服务，工程类未适配
- **评审方法限制**：仅支持综合评分法
- **地区差异限制**：关键词无法区分省份
- **政策变化限制**：知识库需人工更新
- **材料合规限制**：无法校验证明材料有效性
- **语言限制**：仅支持中文

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 轻量级设计（Python Dict + JSON） | 快速迭代，无需数据库依赖 | ✓ Good（原型阶段） |
| 9种评分项与87号令对齐 | 符合法规框架，合规性好 | ✓ Good |
| 排除词机制过滤偏离表 | 减少干扰页面，提高精准度 | ✓ Good |
| 知识库静态存储 | 简单易用 | ⚠️ Revisit（需政策自动更新机制） |
| ProcurementType 枚举顶层架构 | 符合财政部87号令分类 | ✓ Good — v1.1 |
| weight_range 按类型配置 | 货物价格30-50%，服务10-30%合规 | ✓ Good — v1.1 |
| 连续性追踪 + 弱关键词分层 | 解决合同条款页漏检 | ✓ Good — v1.2 |
| bidirectional 双向搜索 | 证明材料可能在标题页之前 | ✓ Good — v1.2 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after v1.2 milestone archived*