"""Social Spark orchestrator agent."""

import os
import pathlib
import sys
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.skills import load_skill_from_dir
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.tools.tool_context import ToolContext
from mcp import StdioServerParameters

from .tools import generate_image

# ---------------------------------------------------------------------------
# 1. 載入 Agent Skills
# ---------------------------------------------------------------------------
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = PROJECT_ROOT / "skills"

skill_toolset = SkillToolset(
    skills=[
        load_skill_from_dir(SKILLS_DIR / "post-formatter"),
        load_skill_from_dir(SKILLS_DIR / "platform-style"),
        load_skill_from_dir(SKILLS_DIR / "brand-voice"),
        load_skill_from_dir(SKILLS_DIR / "poster-style"),
    ],
    tool_filter=["load_skill", "load_skill_resource", "list_skills"],
)

# ---------------------------------------------------------------------------
# 2. 獨立 Web 搜尋 Agent (避免與一般工具混合呼叫)
# ---------------------------------------------------------------------------
search_agent = Agent(
    name="web_researcher",
    model="gemini-2.5-flash",
    description="Researches facts, dates, and context on the web.",
    instruction=(
        "Research the given query and return a concise summary of relevant facts."
    ),
    tools=[google_search],
)

# ---------------------------------------------------------------------------
# 3. 發布工具：Buffer (HTTP MCP) & LinkedIn (Stdio MCP)
# ---------------------------------------------------------------------------
BUFFER_API_KEY = os.environ.get("BUFFER_API_KEY", "")
POST_VIA = os.environ.get("POST_VIA", "").strip().lower()

tools = [
    AgentTool(agent=search_agent),
    generate_image,
    skill_toolset,
]

# 掛載 Buffer MCP
if BUFFER_API_KEY and POST_VIA != "linkedin":
    buffer_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="https://mcp.buffer.com/mcp",
            headers={"Authorization": f"Bearer {BUFFER_API_KEY}"},
        ),
        tool_filter=["get_account", "list_channels", "create_post"],
        require_confirmation=True,
    )
    tools.append(buffer_toolset)

# 掛載 LinkedIn 本地 MCP (Bonus / 支援圖片發布)
if POST_VIA != "buffer":
    MCP_SERVER = PROJECT_ROOT / "mcp" / "linkedin_server.py"
    linkedin_toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[str(MCP_SERVER)],
                env={
                    "DRY_RUN": os.environ.get("DRY_RUN", "true"),
                    "LINKEDIN_ACCESS_TOKEN": os.environ.get(
                        "LINKEDIN_ACCESS_TOKEN", ""
                    ),
                },
            ),
        ),
        tool_filter=["get_profile", "create_post"],
        tool_name_prefix="linkedin",
        require_confirmation=True,
    )
    tools.append(linkedin_toolset)

# ---------------------------------------------------------------------------
# 4. Pipeline Stage 狀態追蹤回呼函式
# ---------------------------------------------------------------------------
_TOOL_STAGES = {
    "web_researcher": "researching",
    "load_skill": "drafting",
    "generate_image": "drafting",
}


def _init_stage(callback_context: CallbackContext) -> None:
    if "pipeline_stage" not in callback_context.state:
        callback_context.state["pipeline_stage"] = "idea"


def _track_stage(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[dict]:
    if tool.name in _TOOL_STAGES:
        tool_context.state["pipeline_stage"] = _TOOL_STAGES[tool.name]
    elif tool.name in ("create_post", "linkedin_create_post"):
        is_error = False
        if isinstance(tool_response, dict):
            is_error = tool_response.get("isError", False)
        if not is_error:
            tool_context.state["pipeline_stage"] = "posted"
    return None


def _stage_after_agent(callback_context: CallbackContext) -> None:
    if callback_context.state.get("pipeline_stage") in ("researching", "drafting"):
        callback_context.state["pipeline_stage"] = "awaiting_approval"


# ---------------------------------------------------------------------------
# 5. Root Agent 核心編排者
# ---------------------------------------------------------------------------
root_agent = Agent(
    name="social_poster",
    model="gemini-2.5-flash",
    description="Helps the user turn an idea into a polished social media post.",
    instruction="""You help the user turn an idea into a social media post.

Tool Calling Rules (Strict):
- You must ONLY call available tools directly using structured function calls.
- NEVER attempt to call 'python_interpreter' or 'google:python_interpreter'.
- Never use Python code to invoke tools. To load a skill, directly invoke the load_skill function tool with skill_name.

Workflow:
1. If the idea needs facts, dates, or context, research it with the web_researcher tool first.
2. When drafting, call load_skill for the relevant skills: post-formatter (structure),
   platform-style (rules for the target platform), and brand-voice (tone).
3. If the user asks for an image, load and follow the poster-style skill, then call
   generate_image with a detailed visual description and tell them where the file was saved.
4. ALWAYS show the finished draft to the user and ask for their approval before any posting action.
   For an immediate post, ask Buffer to publish now rather than schedule.

Posting rules (strict):
- Only post AFTER the user has explicitly approved the exact draft shown to them.
  "Yes", "post it" counts; enthusiasm about the idea does not.
- Publishing routing:
  - If the user asks for an immediate LinkedIn post with an image attached, use the linkedin_create_post tool.
  - For scheduled posts or publishing to other channels, use Buffer's create_post.
- After posting, share the returned confirmation with the user.""",
    tools=tools,
    before_agent_callback=_init_stage,
    after_tool_callback=_track_stage,
    after_agent_callback=_stage_after_agent,
)