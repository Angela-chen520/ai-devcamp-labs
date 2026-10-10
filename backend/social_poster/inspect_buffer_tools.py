
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄：ai-devcamp-labs
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# 確認有沒有讀取到，不印出 Key 本身
print(
    "BUFFER_API_KEY 已設定：",
    bool(os.environ.get("BUFFER_API_KEY"))
)

from .agent import buffer_toolset


async def main():
    print("\n=== Buffer MCP 工具清單 ===")

    try:
        tools = await buffer_toolset.get_tools()

        if not tools:
            print("沒有取得任何工具。")
            return

        for index, tool in enumerate(tools, start=1):
            print(f"\n--- Tool {index} ---")
            print("名稱：", getattr(tool, "name", "(未提供)"))
            print("說明：", getattr(tool, "description", "(未提供)"))
            print("參數：", getattr(tool, "parameters", None))

    except Exception as exc:
        print("取得工具清單失敗：", type(exc).__name__)
        print("錯誤內容：", str(exc))


if __name__ == "__main__":
    asyncio.run(main())