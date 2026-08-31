# models/registry.py
"""
模型注册表：管理模型规格，支持能力查询和选择
增强: 模型特性配置 + 用户可切换
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ModelCapability(Enum):
    """模型能力标签"""
    REASONING = "reasoning"      # 推理
    TOOL_CALL = "tool_call"      # 工具调用
    ROUTING = "routing"          # 路由
    EMBEDDING = "embedding"      # 向量化
    CHAT = "chat"                # 对话
    CODE = "code"                # 代码
    VISION = "vision"            # 视觉


@dataclass
class ModelSpec:
    """模型规格 - 增强特性配置"""
    name: str
    provider: str = "ollama"
    capabilities: List[ModelCapability] = field(default_factory=list)

    # 参数
    temperature: float = 0.2
    timeout: int = 120
    num_predict: int = 4096
    context_window: int = 8192

    # 性能指标
    speed_score: float = 0.5      # 速度评分 (0-1)
    quality_score: float = 0.5    # 质量评分 (0-1)
    cost_score: float = 0.5       # 成本评分 (0-1)
    memory_usage: float = 4.0     # 内存占用 (GB)

    # 权重（用于综合评分）
    speed_weight: float = 0.3
    quality_weight: float = 0.5
    cost_weight: float = 0.2

    enabled: bool = True

    # ✅ 新增: 模型特性描述
    strengths: List[str] = field(default_factory=list)      # 优势
    weaknesses: List[str] = field(default_factory=list)     # 劣势
    best_for: List[str] = field(default_factory=list)       # 最佳用途
    tags: List[str] = field(default_factory=list)           # 标签

    # ✅ 新增: 推荐角色
    recommended_role: str = "chat"  # thinker, doer, router, chat, embed


class ModelRegistry:
    """模型注册表 - 单例"""

    _instance = None
    _models: Dict[str, ModelSpec] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, spec: ModelSpec):
        """注册模型"""
        self._models[spec.name] = spec

    def get(self, name: str) -> Optional[ModelSpec]:
        """获取模型规格"""
        return self._models.get(name)

    def list_all(self) -> List[ModelSpec]:
        """列出所有模型"""
        return [m for m in self._models.values() if m.enabled]

    def list_by_capability(self, capability: ModelCapability) -> List[ModelSpec]:
        """按能力列出模型"""
        return [m for m in self._models.values()
                if capability in m.capabilities and m.enabled]

    def list_by_role(self, role: str) -> List[ModelSpec]:
        """按推荐角色列出模型"""
        return [m for m in self._models.values()
                if m.recommended_role == role and m.enabled]

    def select_best(self, capability: ModelCapability,
                    prefer_speed: bool = False) -> Optional[ModelSpec]:
        """根据能力选择最优模型"""
        candidates = self.list_by_capability(capability)
        if not candidates:
            return None

        if prefer_speed:
            return max(candidates, key=lambda m: m.speed_score)

        def calc_score(m: ModelSpec) -> float:
            return (m.speed_score * m.speed_weight +
                    m.quality_score * m.quality_weight +
                    m.cost_score * m.cost_weight)

        return max(candidates, key=calc_score)

    def get_thinker(self) -> Optional[ModelSpec]:
        """获取默认思考模型"""
        return self.select_best(ModelCapability.REASONING)

    def get_doer(self) -> Optional[ModelSpec]:
        """获取默认执行模型"""
        return self.select_best(ModelCapability.TOOL_CALL)

    def get_router(self) -> Optional[ModelSpec]:
        """获取默认路由模型"""
        return self.select_best(ModelCapability.ROUTING)

    def get_embedding(self) -> Optional[ModelSpec]:
        """获取默认向量模型"""
        return self.select_best(ModelCapability.EMBEDDING)

    def count(self) -> int:
        return len(self._models)

    def clear(self):
        self._models.clear()

    def load_defaults(self):
        """加载默认模型配置 - 包含特性描述"""
        defaults = [
            ModelSpec(
                name="deepseek-r1:8b",
                capabilities=[ModelCapability.REASONING, ModelCapability.CODE],
                temperature=0.2,
                speed_score=0.3,
                quality_score=0.9,
                cost_score=0.6,
                memory_usage=6.0,
                strengths=["推理能力卓越", "代码生成质量高", "深度分析能力强"],
                weaknesses=["速度明显偏慢", "对话体验欠佳", "不支持工具调用", "中文对话能力稍弱"],
                best_for=["复杂推理", "代码生成", "深度分析"],
                recommended_role="thinker",
                tags=["推理", "代码", "深度分析"],
            ),
            ModelSpec(
                name="qwen3.5:9b",
                capabilities=[ModelCapability.TOOL_CALL, ModelCapability.CHAT],
                temperature=0.1,
                speed_score=0.5,
                quality_score=0.85,
                cost_score=0.5,
                memory_usage=8.0,
                strengths=["中英文双语能力强", "工具调用成熟", "指令遵循能力强",
                          "对话体验优秀", "知识广度好"],
                weaknesses=["深度推理能力一般", "创造性相对保守",
                           "代码生成能力中等", "参数量较大"],
                best_for=["工具调用", "对话", "任务执行"],
                recommended_role="doer",
                tags=["工具调用", "对话", "双语"],
            ),
            ModelSpec(
                name="qwen2.5:3b",
                capabilities=[ModelCapability.ROUTING],
                temperature=0.1,
                speed_score=0.85,
                quality_score=0.55,
                cost_score=0.9,
                memory_usage=2.5,
                strengths=["推理速度快", "资源占用低", "基础能力尚可", "训练效率高"],
                weaknesses=["理解能力有限", "生成质量不稳定", "知识储备有限", "不适合复杂任务"],
                best_for=["路由", "简单分类", "快速响应"],
                recommended_role="router",
                tags=["路由", "快速", "轻量"],
            ),
            ModelSpec(
                name="nomic-embed-text:latest",
                capabilities=[ModelCapability.EMBEDDING],
                speed_score=0.8,
                quality_score=0.7,
                cost_score=0.8,
                memory_usage=1.5,
                strengths=["向量化质量好", "速度快", "资源占用低"],
                weaknesses=["仅支持向量化", "不支持对话"],
                best_for=["RAG检索", "语义搜索"],
                recommended_role="embedding",
                tags=["向量化", "RAG", "检索"],
            ),
        ]

        for spec in defaults:
            self.register(spec)

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取模型详细信息（用于 UI 展示）"""
        spec = self.get(model_name)
        if not spec:
            return None

        return {
            "name": spec.name,
            "provider": spec.provider,
            "capabilities": [c.value for c in spec.capabilities],
            "speed_score": spec.speed_score,
            "quality_score": spec.quality_score,
            "cost_score": spec.cost_score,
            "memory_usage": spec.memory_usage,
            "strengths": spec.strengths,
            "weaknesses": spec.weaknesses,
            "best_for": spec.best_for,
            "recommended_role": spec.recommended_role,
            "tags": spec.tags,
        }


# 全局注册表实例
model_registry = ModelRegistry()
model_registry.load_defaults()