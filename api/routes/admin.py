# api/routes/admin.py
"""
管理路由 - 技能/工作流/模型/配置/工具 的 CRUD
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import yaml
import os
import shutil
from pathlib import Path

from core.config import config
from core.logger import agent_logger
from core.paths import get_skills_dir, get_workflows_dir, get_output_dir, get_app_data_dir
from core.router import router as agent_router

# 延迟导入，避免循环依赖
_skill_registry = None
_workflow_registry = None


def get_skill_registry():
    global _skill_registry
    if _skill_registry is None:
        from skills.registry import skill_registry
        _skill_registry = skill_registry
    return _skill_registry


def get_workflow_registry():
    global _workflow_registry
    if _workflow_registry is None:
        from workflows.registry import workflow_registry
        _workflow_registry = workflow_registry
    return _workflow_registry


def find_skill_file(skills_dir: Path, skill_name: str) -> Optional[Path]:
    """
    查找技能文件，支持两种格式：
    1. skills/analyze/skill.yaml (子目录)
    2. skills/analyze.yaml (根目录)
    """
    subdir_path = skills_dir / skill_name / "skill.yaml"
    if subdir_path.exists():
        return subdir_path

    root_path = skills_dir / f"{skill_name}.yaml"
    if root_path.exists():
        return root_path

    return None


def find_skill_dir(skills_dir: Path, skill_name: str) -> Optional[Path]:
    """查找技能目录"""
    subdir_path = skills_dir / skill_name
    if subdir_path.exists() and subdir_path.is_dir():
        return subdir_path
    return None


router = APIRouter()


# ============================================================
# 数据模型
# ============================================================

class SkillCreate(BaseModel):
    name: str
    description: str = ""
    triggers: List[str]
    model: Optional[str] = None
    tools: List[str] = []
    prompt: str = ""
    enabled: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    triggers: Optional[List[str]] = None
    model: Optional[str] = None
    tools: Optional[List[str]] = None
    prompt: Optional[str] = None
    enabled: Optional[bool] = None


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    triggers: List[str]
    steps: List[Dict[str, Any]] = []
    enabled: bool = True


class CloudModelConfig(BaseModel):
    provider: str
    model_name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class PathConfig(BaseModel):
    data_dir: Optional[str] = None
    output_dir: Optional[str] = None


# ============================================================
# 技能管理 API
# ============================================================

@router.get("/admin/skills")
async def list_skills():
    """列出所有技能"""
    registry = get_skill_registry()
    skills = []
    for name, spec in registry._items.items():
        skills.append({
            "name": name,
            "description": getattr(spec, 'description', ''),
            "triggers": getattr(spec, 'triggers', []),
            "model": getattr(spec, 'model', None),
            "tools": getattr(spec, 'tools', []),
            "enabled": getattr(spec, 'enabled', True),
            "prompt": getattr(spec, 'prompt', ''),
        })
    return {"skills": skills, "total": len(skills)}


@router.post("/admin/skills")
async def create_skill(data: SkillCreate):
    """创建新技能"""
    try:
        skills_dir = get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / data.name
        if skill_dir.exists():
            raise HTTPException(status_code=400, detail=f"技能 '{data.name}' 已存在")

        skill_dir.mkdir(parents=True, exist_ok=True)
        filepath = skill_dir / "skill.yaml"

        skill_data = {
            "name": data.name,
            "description": data.description,
            "triggers": data.triggers,
            "model": data.model,
            "tools": data.tools,
            "prompt": data.prompt,
            "enabled": data.enabled,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(skill_data, f, allow_unicode=True, default_flow_style=False)

        from skills.loader import load_skills
        if skills_dir.exists():
            load_skills(str(skills_dir))

        agent_router.refresh_route_map()

        agent_logger.info(f"✅ 创建技能: {data.name}")
        return {"success": True, "message": f"技能 '{data.name}' 已创建", "file": str(filepath)}
    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"创建技能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/skills/{skill_name}")
async def update_skill(skill_name: str, data: SkillUpdate):
    """更新技能"""
    try:
        skills_dir = get_skills_dir()

        filepath = find_skill_file(skills_dir, skill_name)

        if not filepath:
            raise HTTPException(status_code=404, detail=f"技能 '{skill_name}' 不存在")

        with open(filepath, 'r', encoding='utf-8') as f:
            skill_data = yaml.safe_load(f)

        update_dict = data.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                skill_data[key] = value

        if data.name and data.name != skill_name:
            current_dir = filepath.parent
            new_dir = skills_dir / data.name
            if new_dir.exists():
                raise HTTPException(status_code=400, detail=f"技能 '{data.name}' 已存在")
            current_dir.rename(new_dir)
            filepath = new_dir / "skill.yaml"

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(skill_data, f, allow_unicode=True, default_flow_style=False)

        from skills.loader import load_skills
        if skills_dir.exists():
            load_skills(str(skills_dir))

        agent_router.refresh_route_map()

        agent_logger.info(f"✅ 更新技能: {skill_name}")
        return {"success": True, "message": f"技能 '{skill_name}' 已更新"}
    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"更新技能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/skills/{skill_name}")
async def delete_skill(skill_name: str):
    """删除技能"""
    try:
        skills_dir = get_skills_dir()

        filepath = find_skill_file(skills_dir, skill_name)

        if not filepath:
            raise HTTPException(status_code=404, detail=f"技能 '{skill_name}' 不存在")

        parent_dir = filepath.parent
        if parent_dir != skills_dir and parent_dir.exists():
            shutil.rmtree(parent_dir)
        else:
            os.remove(filepath)

        from skills.loader import load_skills
        if skills_dir.exists():
            load_skills(str(skills_dir))

        agent_router.refresh_route_map()

        agent_logger.info(f"✅ 删除技能: {skill_name}")
        return {"success": True, "message": f"技能 '{skill_name}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"删除技能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 工作流管理 API
# ============================================================

@router.get("/admin/workflows")
async def list_workflows():
    """列出所有工作流"""
    registry = get_workflow_registry()
    workflows = []
    for name, spec in registry._items.items():
        workflows.append({
            "name": name,
            "description": getattr(spec, 'description', ''),
            "triggers": getattr(spec, 'triggers', []),
            "steps": len(getattr(spec, 'steps', [])),
            "enabled": getattr(spec, 'enabled', True),
        })
    return {"workflows": workflows, "total": len(workflows)}


@router.post("/admin/workflows")
async def create_workflow(data: WorkflowCreate):
    """创建工作流"""
    try:
        workflows_dir = get_workflows_dir()
        workflows_dir.mkdir(parents=True, exist_ok=True)

        filepath = workflows_dir / f"{data.name}.yaml"

        if filepath.exists():
            raise HTTPException(status_code=400, detail=f"工作流 '{data.name}' 已存在")

        workflow_data = {
            "name": data.name,
            "description": data.description,
            "triggers": data.triggers,
            "steps": data.steps,
            "enabled": data.enabled,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_data, f, allow_unicode=True, default_flow_style=False)

        from workflows.loader import load_workflows
        if workflows_dir.exists():
            load_workflows(str(workflows_dir))

        agent_router.refresh_route_map()

        agent_logger.info(f"✅ 创建工作流: {data.name}")
        return {"success": True, "message": f"工作流 '{data.name}' 已创建"}
    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/workflows/{workflow_name}")
async def delete_workflow(workflow_name: str):
    """删除工作流"""
    try:
        workflows_dir = get_workflows_dir()
        filepath = workflows_dir / f"{workflow_name}.yaml"

        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"工作流 '{workflow_name}' 不存在")

        os.remove(filepath)

        from workflows.loader import load_workflows
        if workflows_dir.exists():
            load_workflows(str(workflows_dir))

        agent_router.refresh_route_map()

        agent_logger.info(f"✅ 删除工作流: {workflow_name}")
        return {"success": True, "message": f"工作流 '{workflow_name}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"删除工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 模型配置 API
# ============================================================

@router.get("/admin/models")
async def list_models():
    """列出所有可用模型（包含本地和云模型）"""
    from core.health import health_check

    available = health_check.get_available_models(force_refresh=True)
    local_models = []
    for m in available:
        name = m.get('name', '')
        if name and 'embed' not in name.lower() and 'nomic' not in name.lower():
            local_models.append({
                "name": name,
                "size": m.get('size', 0),
                "modified": m.get('modified', ''),
                "type": "local"
            })

    cloud_models = config.get("models.cloud", [])
    cloud_model_list = []
    for cloud in cloud_models:
        cloud_model_list.append({
            "name": cloud.get("model_name"),
            "provider": cloud.get("provider"),
            "type": "cloud"
        })

    all_models = local_models + cloud_model_list
    current = config.get("models.default_model")

    available_names = [m.get('name') for m in all_models]
    if current not in available_names and all_models:
        current = all_models[0].get('name')
        config.set("models.default_model", current)
        config.save()

    return {
        "local": local_models,
        "cloud": cloud_models,
        "all": all_models,
        "current": current,
        "providers": ["ollama", "openai", "deepseek", "custom"]
    }


@router.post("/admin/models/switch")
async def switch_model(model_name: str = Body(..., embed=True)):
    """切换默认模型"""
    try:
        config.set("models.default_model", model_name)
        config.save()
        agent_logger.info(f"✅ 切换模型: {model_name}")
        return {"success": True, "message": f"已切换到 '{model_name}'"}
    except Exception as e:
        agent_logger.error(f"切换模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/models/cloud")
async def configure_cloud_model(data: CloudModelConfig):
    """配置云模型 API"""
    try:
        cloud_models = config.get("models.cloud", [])

        found = False
        for i, m in enumerate(cloud_models):
            if m.get("provider") == data.provider:
                cloud_models[i] = data.dict()
                found = True
                break

        if not found:
            cloud_models.append(data.dict())

        config.set("models.cloud", cloud_models)
        config.save()

        agent_logger.info(f"✅ 配置云模型: {data.provider}")
        return {"success": True, "message": f"云模型 '{data.provider}' 已配置"}
    except Exception as e:
        agent_logger.error(f"配置云模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/models/cloud/{provider}")
async def delete_cloud_model(provider: str):
    """删除云模型配置"""
    try:
        cloud_models = config.get("models.cloud", [])
        cloud_models = [m for m in cloud_models if m.get("provider") != provider]
        config.set("models.cloud", cloud_models)
        config.save()

        agent_logger.info(f"✅ 删除云模型: {provider}")
        return {"success": True, "message": f"云模型 '{provider}' 已删除"}
    except Exception as e:
        agent_logger.error(f"删除云模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 路径配置 API
# ============================================================

@router.get("/admin/paths")
async def get_paths():
    """获取当前路径配置"""
    from core.paths import get_app_data_dir, get_output_dir, get_skills_dir, get_workflows_dir

    return {
        "data_dir": str(get_app_data_dir()),
        "output_dir": str(get_output_dir()),
        "skills_dir": str(get_skills_dir()),
        "workflows_dir": str(get_workflows_dir()),
    }


@router.post("/admin/paths")
async def update_paths(data: PathConfig):
    """更新路径配置"""
    try:
        if data.data_dir:
            config.set("paths.data_dir", data.data_dir)
        if data.output_dir:
            config.set("paths.output_dir", data.output_dir)
        config.save()

        agent_logger.info(f"✅ 更新路径: data={data.data_dir}, output={data.output_dir}")
        return {"success": True, "message": "路径已更新"}
    except Exception as e:
        agent_logger.error(f"更新路径失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 数据/输出文件管理 API
# ============================================================

@router.get("/admin/files/data")
async def list_data_files():
    """列出 data 目录中的文件"""
    from core.paths import get_app_data_dir

    data_dir = get_app_data_dir()
    files = []

    if data_dir.exists():
        for root, dirs, filenames in os.walk(data_dir):
            for filename in filenames:
                filepath = Path(root) / filename
                try:
                    rel_path = filepath.relative_to(data_dir)
                    files.append({
                        "name": filename,
                        "path": str(rel_path),
                        "size": filepath.stat().st_size,
                        "modified": filepath.stat().st_mtime,
                    })
                except:
                    pass

    files.sort(key=lambda x: x.get('modified', 0), reverse=True)

    return {"files": files, "total": len(files), "root": str(data_dir)}


@router.get("/admin/files/output")
async def list_output_files():
    """列出 output 目录中的文件"""
    from core.paths import get_output_dir

    output_dir = get_output_dir()
    files = []

    if output_dir.exists():
        for filepath in output_dir.iterdir():
            if filepath.is_file():
                files.append({
                    "name": filepath.name,
                    "size": filepath.stat().st_size,
                    "modified": filepath.stat().st_mtime,
                })

    files.sort(key=lambda x: x.get('modified', 0), reverse=True)

    return {"files": files, "total": len(files), "root": str(output_dir)}


@router.delete("/admin/files/output/{filename}")
async def delete_output_file(filename: str):
    """删除 output 目录中的文件"""
    from core.paths import get_output_dir

    output_dir = get_output_dir()
    filepath = output_dir / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"文件 '{filename}' 不存在")

    os.remove(filepath)
    agent_logger.info(f"✅ 删除输出文件: {filename}")
    return {"success": True, "message": f"文件 '{filename}' 已删除"}


@router.post("/admin/files/output/clear")
async def clear_output():
    """清空 output 目录"""
    from core.paths import get_output_dir

    output_dir = get_output_dir()
    count = 0

    if output_dir.exists():
        for filepath in output_dir.iterdir():
            if filepath.is_file():
                os.remove(filepath)
                count += 1

    agent_logger.info(f"✅ 清空 output 目录: {count} 个文件")
    return {"success": True, "message": f"已清空 {count} 个文件"}


# ============================================================
# 工具管理 API
# ============================================================

@router.get("/admin/tools")
async def admin_list_tools():
    """列出所有工具（包括自定义工具）"""
    from tools.registry import tool_registry

    tools = []
    for spec in tool_registry.list_all():
        # 判断是否为内置工具
        is_builtin = spec.name in agent_router.TOOL_ALIASES
        display_name = agent_router.get_tool_alias(spec.name) if hasattr(agent_router, 'get_tool_alias') else spec.name
        tools.append({
            "name": spec.name,
            "display_name": display_name,
            "description": spec.description,
            "is_builtin": is_builtin,
        })
    return {"tools": tools, "total": len(tools)}


@router.get("/admin/tools/custom")
async def admin_list_custom_tools():
    """列出自定义工具"""
    try:
        from tools.loader import get_custom_tools_info
        custom_tools = get_custom_tools_info()
        return {"tools": custom_tools, "total": len(custom_tools)}
    except ImportError:
        return {"tools": [], "total": 0}


@router.post("/admin/tools/reload")
async def admin_reload_tools():
    """热加载自定义工具"""
    try:
        from tools.loader import load_custom_tools
        loaded = load_custom_tools()

        # 刷新工具别名
        if hasattr(agent_router, 'refresh_tool_aliases'):
            agent_router.refresh_tool_aliases()
        else:
            agent_router.refresh_route_map()

        return {"success": True, "message": f"已加载 {loaded} 个自定义工具", "loaded": loaded}
    except Exception as e:
        agent_logger.error(f"热加载工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/tools/clear")
async def admin_clear_tools():
    """清空所有自定义工具文件（谨慎使用）"""
    try:
        import shutil
        from tools.loader import BUILTIN_TOOLS

        custom_dir = Path("./tools")
        if not custom_dir.exists():
            return {"success": True, "message": "没有自定义工具"}

        # 删除所有非内置工具文件
        deleted = 0
        for tool_file in custom_dir.glob("*.py"):
            if tool_file.name in BUILTIN_TOOLS or tool_file.name.startswith("__"):
                continue
            os.remove(tool_file)
            deleted += 1

        # 重新加载（清空后只有内置工具）
        agent_router.refresh_tool_aliases()
        agent_logger.info(f"✅ 清空自定义工具: {deleted} 个文件")
        return {"success": True, "message": f"已清空 {deleted} 个自定义工具", "deleted": deleted}
    except Exception as e:
        agent_logger.error(f"清空自定义工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 热加载 API
# ============================================================

@router.post("/admin/reload")
async def reload_all():
    """热加载所有技能、工作流和工具"""
    try:
        from skills.loader import load_skills
        from workflows.loader import load_workflows
        from tools.loader import load_custom_tools

        skills_dir = get_skills_dir()
        workflows_dir = get_workflows_dir()

        if skills_dir.exists():
            load_skills(str(skills_dir))

        if workflows_dir.exists():
            load_workflows(str(workflows_dir))

        # 热加载工具
        load_custom_tools()

        # 刷新路由映射
        agent_router.refresh_route_map()

        # 刷新工具别名
        if hasattr(agent_router, 'refresh_tool_aliases'):
            agent_router.refresh_tool_aliases()

        agent_logger.info("✅ 热加载完成（技能 + 工作流 + 工具）")
        return {"success": True, "message": "技能、工作流和工具已重新加载"}
    except Exception as e:
        agent_logger.error(f"热加载失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))