# core/unified_memory.py
"""
统一知识库：记忆 + RAG + 经验 统一存储和检索
增强: 自动提取用户画像 + 经验规则 + 定时整合到 RAG
"""

import json
import os
import uuid
import pickle
import re
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from difflib import SequenceMatcher
from collections import defaultdict

from core.logger import agent_logger
from core.config import config


class UnifiedMemory:
    """
    统一知识库
    增强: 自动提取用户画像、经验规则、定时整合到 RAG
    """

    def __init__(self, filepath: str = "./data/unified_memory/knowledge.json"):
        self.filepath = filepath
        self.rules_file = "./data/memory/failure_rules.json"
        self._cache = None
        self._vectors = None
        self._vector_cache_file = "./data/unified_memory/vectors.pkl"
        self._embedding_model = None
        self._ensure()

        self.KNOWLEDGE_TYPES = {
            "user_info": "用户个人信息",
            "document": "文档知识",
            "rule": "经验规则",
            "experience": "历史经验",
            "preference": "用户偏好",
        }

        self.USER_INFO_CATEGORIES = {
            "name": "名字",
            "age": "年龄",
            "birthday": "生日",
            "school": "学校",
            "major": "专业",
            "profession": "职业",
            "hobby": "爱好",
            "hometown": "家乡",
            "email": "邮箱",
            "phone": "手机号",
            "address": "地址",
            "company": "公司",
            "position": "职位",
        }

        # ✅ 加载向量缓存
        self._load_vectors_cache()

        # ✅ 启动定时整合线程 (每10分钟)
        self._integrator_running = True
        self._integrator_thread = threading.Thread(
            target=self._integrator_loop,
            daemon=True,
            name="UnifiedMemoryIntegrator"
        )
        self._integrator_thread.start()
        agent_logger.info("🧠 统一知识库定时整合线程已启动")

    def _ensure(self):
        os.makedirs(os.path.dirname(self.filepath) or '.', exist_ok=True)
        if not os.path.exists(self.filepath):
            self._save([])

    def _load_vectors_cache(self):
        """使用 pickle 加载向量缓存"""
        try:
            if os.path.exists(self._vector_cache_file):
                with open(self._vector_cache_file, 'rb') as f:
                    self._vectors = pickle.load(f)
                agent_logger.debug(f"加载向量缓存: {len(self._vectors)} 个向量")
            else:
                self._vectors = None
        except (OSError, IOError, pickle.PickleError) as e:
            agent_logger.debug(f"加载向量缓存失败: {e}")
            self._vectors = None

    def _save_vectors_cache(self, vectors: List[List[float]]):
        """使用 pickle 保存向量缓存"""
        try:
            with open(self._vector_cache_file, 'wb') as f:
                pickle.dump(vectors, f)
            agent_logger.debug(f"保存向量缓存: {len(vectors)} 个向量")
        except (OSError, IOError, pickle.PickleError) as e:
            agent_logger.debug(f"保存向量缓存失败: {e}")

    def _get_embeddings(self):
        if self._embedding_model is None:
            try:
                from langchain_ollama import OllamaEmbeddings
                embedding_model = config.get("models.embedding", "nomic-embed-text:latest")
                self._embedding_model = OllamaEmbeddings(model=embedding_model)
            except Exception as e:
                agent_logger.warning(f"Embedding 模型加载失败: {e}")
                self._embedding_model = None
        return self._embedding_model

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        import numpy as np
        a = np.array(a)
        b = np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _load_vectors(self, items: List[Dict]) -> List[List[float]]:
        """加载向量，优先从缓存读取"""
        if self._vectors is not None and len(self._vectors) == len(items):
            return self._vectors

        embeddings = self._get_embeddings()
        vectors = []

        for item in items:
            content = item.get("content", "")
            if content:
                try:
                    vec = embeddings.embed_query(content) if embeddings else None
                    vectors.append(vec if vec else [])
                except Exception:
                    vectors.append([])
            else:
                vectors.append([])

        self._vectors = vectors
        self._save_vectors_cache(vectors)
        return vectors

    def _load(self) -> List[Dict]:
        if self._cache is not None:
            return self._cache

        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache = data if isinstance(data, list) else []
                    return self._cache
            except (json.JSONDecodeError, ValueError):
                try:
                    os.remove(self.filepath)
                except (OSError, IOError):
                    pass

        self._cache = []
        return self._cache

    def _save(self, items: List[Dict]):
        self._cache = items
        self._vectors = None
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    # ============================================================
    # ✅ 定时整合到 RAG
    # ============================================================

    def _integrator_loop(self):
        """定时整合循环 - 每10分钟"""
        while self._integrator_running:
            try:
                time.sleep(600)  # 10分钟
                self._periodic_integrate()
            except Exception as e:
                agent_logger.warning(f"记忆整合循环异常: {e}")

    def _periodic_integrate(self):
        """
        定时整合：用户画像 + 经验规则 → RAG
        """
        try:
            from core.rag import rag

            agent_logger.info("🔄 开始定时整合记忆到 RAG...")

            items = self._load()
            unvectorized = [
                item for item in items
                if not item.get("vectorized") and not item.get("archived")
            ]

            if not unvectorized:
                agent_logger.debug("📭 没有需要整合的记忆")
                return

            # 分类处理
            user_infos = [item for item in unvectorized if item.get("type") == "user_info"]
            rules = [item for item in unvectorized if item.get("type") == "rule"]
            others = [item for item in unvectorized if item.get("type") not in ["user_info", "rule"]]

            # 整合用户画像
            for item in user_infos[:20]:  # 每次最多20条
                content = item.get("content", "")
                if content and len(content.strip()) > 5:
                    self._vectorize_to_rag(content, {"type": "user_info", "category": item.get("category", "")})

            # 整合经验规则
            for item in rules[:10]:
                content = item.get("content", "")
                if content and len(content.strip()) > 5:
                    self._vectorize_to_rag(content, {"type": "rule"})

            # 整合其他记忆
            for item in others[:10]:
                content = item.get("content", "")
                if content and len(content.strip()) > 10:
                    self._vectorize_to_rag(content, {"type": item.get("type", "memory")})

            # 标记已整合
            for item in unvectorized[:40]:
                item["vectorized"] = True
                item["integrated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self._save(items)
            agent_logger.info(f"✅ 整合 {min(len(unvectorized), 40)} 条记忆到 RAG")

        except Exception as e:
            agent_logger.warning(f"定时整合失败: {e}")

    def _vectorize_to_rag(self, content: str, metadata: Dict = None):
        # ✅ 异步执行，不阻塞主线程
        import threading
        threading.Thread(target=self._vectorize_async, args=(content, metadata), daemon=True).start()

    def _vectorize_async(self, content: str, metadata: Dict = None):
        """实际的向量化逻辑（后台线程执行）"""
        try:
            from core.rag import rag
            if not content or len(content.strip()) < 5:
                return
            import uuid
            doc_id = f"mem_{uuid.uuid4().hex[:8]}"
            rag.add("memory", {doc_id: content})
            agent_logger.debug(f"✅ 向量化: {content[:50]}...")
        except Exception as e:
            agent_logger.debug(f"向量化失败: {e}")

    # ============================================================
    # 自动提取用户画像
    # ============================================================

    def auto_extract_and_save(self, text: str) -> str:
        """自动提取并保存用户信息"""
        # 如果是问句，不提取
        query_patterns = ["什么", "吗", "？", "?", "哪", "多", "几", "怎么", "如何", "谁", "哪里", "什么时候"]
        if any(p in text for p in query_patterns):
            return ""

        # 检查是否包含个人信息关键词
        profile_keywords = ["名字", "姓名", "叫", "岁", "年龄", "生日", "学校", "大学",
                            "专业", "工作", "职业", "爱好", "喜欢", "家乡", "邮箱",
                            "手机", "电话", "地址", "住在", "公司", "职位"]

        if not any(kw in text for kw in profile_keywords):
            return ""

        extracted = self._extract_with_rules(text)

        # 如果规则提取失败，尝试 LLM 提取
        if not extracted:
            extracted = self._extract_with_llm(text)

        if not extracted:
            return ""

        saved = []
        items = self._load()

        for cat, display, value in extracted:
            if not value or len(value) < 2:
                continue

            # 检查是否已存在
            found = False
            for item in items:
                if item.get("category") == cat and item.get("type") == "user_info":
                    # 更新
                    item["content"] = value
                    item["value"] = value
                    item["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    item["vectorized"] = False  # 需要重新向量化
                    found = True
                    break

            if not found:
                items.append({
                    "id": str(uuid.uuid4())[:8],
                    "content": value,
                    "type": "user_info",
                    "category": cat,
                    "source": "auto",
                    "metadata": {},
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "vectorized": False,
                    "value": value,
                    "display_name": display
                })

            saved.append(f"{display}：{value}")

        if saved:
            self._save(items)
            self._vectors = None
            return f"📝 已更新用户信息：{', '.join(saved)}"

        return ""

    def _extract_with_rules(self, text: str) -> List[Tuple[str, str, str]]:
        """使用规则提取用户信息"""
        from core.memory_rules import memory_rules

        extracted = []
        for mem_type in memory_rules.types.values():
            for kw in mem_type.keywords:
                if kw in text:
                    value = memory_rules.extract_value(text, mem_type)
                    if value:
                        extracted.append((mem_type.name, mem_type.display_name, value))
                        break
        return extracted

    def _extract_with_llm(self, text: str) -> List[Tuple[str, str, str]]:
        """使用 LLM 提取用户信息"""
        try:
            from models.manager import model_manager
            from core.health import health_check

            router = model_manager.get_router()
            if not router:
                return []

            prompt = f"""从以下对话中提取用户个人信息，返回 JSON。

【对话】：{text}

【要求】：
1. 识别：姓名、年龄、生日、学校、专业、职业、爱好、家乡、邮箱、公司、职位
2. 只返回 JSON: {{"category": "name|age|birthday|school|major|profession|hobby|hometown|email|company|position", "content": "提取的内容"}}
3. 如果没有，返回 {{"found": false}}
4. 只返回 JSON，不要其他内容

【返回】："""

            result, error = health_check.safe_call(router.invoke, prompt, max_retries=1)

            if not error and result:
                import json
                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if data.get("found") is not False and data.get("category") and data.get("content"):
                        category = data.get("category")
                        content = data.get("content")
                        if len(content) > 1 and content not in ["？", "?", "我的", "你的"]:
                            display = self.USER_INFO_CATEGORIES.get(category, category)
                            return [(category, display, content)]
        except Exception as e:
            agent_logger.debug(f"LLM提取失败: {e}")

        return []

    # ============================================================
    # 自动提取经验规则
    # ============================================================

    def learn_rule_from_feedback(self, action: str, result: str, success: bool):
        """
        从反馈中学习经验规则

        Args:
            action: 执行的动作
            result: 执行结果
            success: 是否成功
        """
        if success:
            rule = f"✅ 成功经验: {action[:50]} → {result[:50]}"
        else:
            rule = f"❌ 失败教训: {action[:50]} → {result[:50]}"

        self.add_rule(rule)

        #  同时记录到 RAG
        self._vectorize_to_rag(rule, {"type": "rule", "success": success})

    def add_rule(self, content: str) -> str:
        """添加经验规则"""
        return self.add(content, "rule", "rule", "manual")

    def get_rules_by_context(self, context: str, limit: int = 5) -> str:
        """根据上下文获取相关规则"""
        results = self.search(context, types=["rule"], k=limit)

        if not results:
            return ""

        lines = ["【经验规则】"]
        for r in results:
            content = r.get("content", "")
            if content:
                lines.append(f"- {content}")

        return "\n".join(lines)

    def add(self, content: str, knowledge_type: str = "user_info",
            category: str = None, source: str = "auto",
            metadata: Dict = None) -> str:
        items = self._load()
        item_id = str(uuid.uuid4())[:8]

        entry = {
            "id": item_id,
            "content": content,
            "type": knowledge_type,
            "category": category or "general",
            "source": source,
            "metadata": metadata or {},
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vectorized": False,
        }

        if knowledge_type == "user_info" and category:
            entry["value"] = content
            entry["display_name"] = self.USER_INFO_CATEGORIES.get(category, category)

        for i, existing in enumerate(items):
            if existing.get("content") == content and existing.get("type") == knowledge_type:
                items[i] = entry
                self._save(items)
                self._vectors = None
                return f"✅ 已更新知识（共{len(items)}条）"

        items.append(entry)
        if len(items) > 2000:
            items = items[-1000:]
        self._save(items)
        self._vectors = None
        return f"✅ 已添加知识（共{len(items)}条）"

    # ============================================================
    # 检索方法
    # ============================================================

    def search(self, query: str, types: List[str] = None,
               categories: List[str] = None, k: int = 5) -> List[Dict]:
        """搜索记忆（关键词 + 向量 + 模糊）"""
        items = self._load()
        if not items:
            return []

        filtered = items
        if types:
            filtered = [item for item in filtered if item.get("type") in types]
        if categories:
            filtered = [item for item in filtered if item.get("category") in categories]

        if not filtered:
            return []

        query_lower = query.lower()
        keyword_results = []
        for item in filtered:
            content = item.get("content", "").lower()
            if query_lower in content:
                keyword_results.append(item)

        if keyword_results:
            return keyword_results[:k]

        # 向量检索
        embeddings = self._get_embeddings()
        if embeddings and len(filtered) > 1:
            try:
                query_vec = embeddings.embed_query(query)
                if query_vec:
                    if self._vectors is None or len(self._vectors) != len(filtered):
                        self._vectors = self._load_vectors(filtered)

                    similarities = []
                    for i, vec in enumerate(self._vectors):
                        if vec and len(vec) > 0:
                            sim = self._cosine_similarity(query_vec, vec)
                            similarities.append((i, sim))
                        else:
                            similarities.append((i, 0))

                    similarities.sort(key=lambda x: x[1], reverse=True)

                    results = []
                    threshold = 0.55
                    for idx, sim in similarities[:k]:
                        if sim >= threshold:
                            results.append(filtered[idx])

                    if results:
                        return results
            except Exception as e:
                agent_logger.debug(f"向量检索失败: {e}")

        # 模糊匹配
        fuzzy_results = []
        for item in filtered:
            content = item.get("content", "")
            score = SequenceMatcher(None, query_lower, content.lower()).ratio()
            if score > 0.3:
                fuzzy_results.append((score, item))

        fuzzy_results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in fuzzy_results[:k]]

    def search_as_text(self, query: str, types: List[str] = None, k: int = 3) -> str:
        """搜索记忆（返回文本格式）"""
        results = self.search(query, types, k=k)
        if not results:
            return ""

        lines = ["【相关知识】"]
        for item in results:
            content = item.get("content", "")
            item_type = item.get("type", "unknown")
            category = item.get("category", "")

            if item_type == "user_info":
                display = self.USER_INFO_CATEGORIES.get(category, category)
                lines.append(f"- [{display}] {content}")
            else:
                lines.append(f"- {content}")

        return "\n".join(lines)

    def get_all(self) -> List[Dict]:
        """获取所有记忆条目"""
        return self._load()

    def get_by_type(self, knowledge_type: str) -> List[Dict]:
        """按类型获取记忆"""
        items = self._load()
        return [item for item in items if item.get("type") == knowledge_type]

    def get_user_info(self) -> List[Dict]:
        """获取所有用户信息"""
        return self.get_by_type("user_info")

    def get_profile(self) -> Dict[str, str]:
        """获取用户画像（键值对）"""
        items = self._load()
        profile = {}

        for item in items:
            if item.get("type") != "user_info":
                continue

            category = item.get("category")
            content = item.get("content")
            display_name = self.USER_INFO_CATEGORIES.get(category, category)

            if category and content:
                profile[display_name] = content

        return profile

    def get_profile_summary(self) -> str:
        """获取用户画像摘要文本"""
        profile = self.get_profile()
        if not profile:
            return ""

        lines = ["【用户画像】"]
        priority = ["名字", "年龄", "生日", "学校", "专业", "工作", "爱好", "家乡", "邮箱", "手机号"]

        for key in priority:
            if key in profile:
                lines.append(f"- {key}：{profile[key]}")

        for key, value in profile.items():
            if key not in priority:
                lines.append(f"- {key}：{value}")

        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        items = self._load()
        stats = defaultdict(int)
        for item in items:
            stats[item.get("type", "unknown")] += 1

        rule_items = [item for item in items if item.get("type") == "rule"]
        success_rules = [r for r in rule_items if "成功" in r.get("content", "")]
        failure_rules = [r for r in rule_items if "失败" in r.get("content", "")]

        return {
            "total": len(items),
            "by_type": dict(stats),
            "rules": {
                "total": len(rule_items),
                "success": len(success_rules),
                "failure": len(failure_rules),
            }
        }

    def clear(self) -> str:
        """清空所有知识"""
        self._save([])
        self._vectors = None
        if os.path.exists(self._vector_cache_file):
            os.remove(self._vector_cache_file)
        return "✅ 已清空所有知识"

    def delete(self, item_id: str) -> str:
        """删除指定条目"""
        items = self._load()
        for i, item in enumerate(items):
            if item.get("id") == item_id:
                items.pop(i)
                self._save(items)
                self._vectors = None
                return f"✅ 已删除知识 {item_id}"
        return f"❌ 未找到知识 {item_id}"

    def shutdown(self):
        """关闭定时整合线程"""
        self._integrator_running = False
        if self._integrator_thread:
            self._integrator_thread.join(timeout=2)
        agent_logger.info("🧠 统一知识库定时整合线程已停止")


unified = UnifiedMemory()