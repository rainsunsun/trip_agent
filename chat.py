import sys
import os
import uuid

# 自动处理路径，防止 ModuleNotFoundError
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.append(root_path)

from backend.app.agents.trip_planner_agent import MultiAgentPlanner

def start_interactive_chat():
    planner = MultiAgentPlanner()
    # 为当前终端会话生成一个唯一的 ID
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("="*50)
    print("👋 欢迎来到您的私人旅行规划助理！(终端实战版)")
    print(f"会话ID: {thread_id} | 记忆功能: 已开启")
    print("="*50)

    # 简单维护一个会话状态
    current_city = None

    while True:
        user_input = input("\n👤 您: ").strip()
        if user_input.lower() in ["exit", "quit", "退出"]: break

        # 简单意图：如果是第一次说话，假设是城市
        if not current_city:
            current_city = user_input # 实际应由 LLM 提取，这里先简化
        
        inputs = {
            "city": current_city,
            "history": [{"role": "user", "content": user_input}]
        }

        # 启动多 Agent 协作流
        result = planner.graph.invoke(inputs, config=config)
        
        print("\n" + "-"*30)
        print(f"🤖 助手: {result['plan_text']}")
        print("-"*30)

if __name__ == "__main__":
    start_interactive_chat()