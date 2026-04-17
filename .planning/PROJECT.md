# PageIndex 采购评分项知识库系统

## What This Is

PageIndex 是一个**向量无关、基于推理的 RAG 系统**，专门用于政府采购响应文件的智能检索。系统通过构建层级树结构索引，模拟人类专家导航和提取知识的方式，解决评审专家需要在有限时间内快速定位评分项页码的核心痛点。

当前版本聚焦**货物和服务类采购**，采用综合评分法，支持扫描件 PDF 检索。

## Core Value

**让评审专家快速定位评分项页码**——这是政府采购评审效率提升的关键需求。

## Current Milestone: v1.1 货物/服务政府采购增强

**Goal:** 为货物类和服务类政府采购增加类型分类、权重差异配置和政策性评分项

**Target features:**
- 采购类型分类（货物/服务）— 顶层架构增加类型分类
- 权重差异配置 — 货物价格权重高（30-50%），服务人员权重高（10-25%）
- 政策性评分项 — 小微企业声明函、绿色产品认证

**预估时间:** 1-2周

## Requirements

### Validated

<!-- 已验证的功能，从现有代码推断 -->

- ✓ **基础树结构索引** — 从 PDF 生成层级树结构（类似目录） — v1.0
- ✓ **视觉检索（VisionPageIndex）** — 直接处理 PDF 页面图片，支持扫描件 — v1.0
- ✓ **多轮扩展检索** — 标题页 + 证明材料页自动合并 — v1.0
- ✓ **采购评分项知识库** — 9种评分项映射（人员配备、类似业绩、设备能力等） — v1.0
- ✓ **关键词排除机制** — 过滤偏离表、响应表等干扰页面 — v1.0
- ✓ **OpenAI Agents SDK 集成** — 支持 Chat Completions API — v1.0
- ✓ **LiteLLM 兼容** — 支持阿里云 DashScope 等国产大模型 — v1.0
- ✓ **工作区持久化** — 索引缓存避免重复生成 — v1.0
- ✓ **知识库构建工具** — TenderParser、KeywordDiscovery、KBValidator、KBManager、ExpertKBEnricher — v1.0

### Active

<!-- v1.1 里程碑目标（基于研究建议调整） -->

- [ ] **TYPE-01**: 系统支持采购类型分类（货物类/服务类）
- [ ] **TYPE-02**: 评分项权重按采购类型差异化配置
- [ ] **POLICY-01**: 新增政策性评分项（中小企业声明函）

### Deferred to v1.x

<!-- 研究建议延后 -->

- **POLICY-02 绿色产品认证** — 需品目清单数据库支持，延后到 v1.x

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
*Last updated: 2026-04-17 after milestone v1.1 initialization*