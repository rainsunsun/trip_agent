import json
import operator
import subprocess
import os
import re
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 自定义 MCPTool 包装器，以防外部库缺失
class MCPTool:
    def __init__(self, name: str, server_command: List[str], env: Dict[str, str]):
        self.name = name
        self.server_command = server_command
        self.env = env

    def run(self, params: Dict[str, Any]) -> str:
        """模拟调用 MCP Server"""
        # 实际生产中应通过 stdio 或 http 与 MCP Server 通信
        # 这里为了演示全链路，我们使用 subprocess 模拟
        tool_name = params.get("tool_name")
        args = params.get("arguments", {})
        
        print(f"🔌 [MCP] 调用工具: {tool_name}, 参数: {args}")
        
        # 模拟高德地图的返回数据
        if tool_name == "maps_weather":
            return f"{args.get('city')}天气：晴，20-25度，适宜旅游。"
        elif tool_name == "maps_text_search":
            return f"{args.get('city')}景点搜索结果：1. 外滩 2. 豫园 3. 上海博物馆。"
        elif tool_name == "maps_direction":
            return "从外滩到豫园：打车约 15 分钟，地铁 10 号线直达。"
        
        return "Tool output placeholder"

from ..services.llm_service import get_llm
from ..config import get_settings
from ..models.schemas import (
    TripRequest, 
    TaskDecomposition, 
    TripPlan, 
    ReflectionResult
)
from ..services.guardrails import Guardrails
from ..services.evals import TripEvaluator

# --- 1. 定义状态 ---
class AgentState(TypedDict, total=False):
    # 原始输入
    user_input: str
    # 结构化需求
    request: TripRequest
    # 任务拆解
    decomposition: TaskDecomposition
    # 外部工具数据
    weather_data: str
    poi_data: str
    route_data: str
    # 最终计划 (Pydantic 模型)
    final_plan: TripPlan
    # 反思结果
    reflection: ReflectionResult
    # 评测指标
    metrics: Dict[str, float]
    # 历史记录
    history: Annotated[List[Dict[str, str]], operator.add]
    # 内部控制
    retry_count: int
    tool_call_count: int

# --- 2. 多智能体规划器 ---
class MultiAgentPlanner:
    def __init__(self):
        settings = get_settings()
        self.llm = get_llm()
        self.checkpointer = MemorySaver()
        
        # 初始化 MCP 工具 (通过 hello-agents 协议)
        self.amap_tool = MCPTool(
            name="amap",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key}
        )
        self.graph = self._build_graph()

    def _call_tool(self, tool_name: str, args: dict, state: AgentState):
        if state.get("tool_call_count", 0) >= 10: # 熔断限制
            return "Error: Tool call limit reached."
        
        state["tool_call_count"] = state.get("tool_call_count", 0) + 1
        try:
            return self.amap_tool.run({"action": "call_tool", "tool_name": tool_name, "arguments": args})
        except Exception as e:
            return f"Tool error: {str(e)}"

    # --- 节点定义 ---

    def _extract_json(self, text: str) -> dict:
        """从字符串中提取 JSON 内容"""
        try:
            # 1. 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 2. 尝试提取 ```json ... ``` 块
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            # 3. 尝试提取第一个 { ... }
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            return {}

    def analyzer_node(self, state: AgentState):
        """需求解析 Agent：将模糊的用户输入转化为结构化需求"""
        print("🔍 [Demand Analyzer] 解析用户意图...")
        # 1. 安全护栏校验
        if not Guardrails.validate_input(state["user_input"]):
            print("🛑 [Guardrails] 输入内容包含敏感信息或不合法，已拦截。")
            raise ValueError("Input blocked by safety guardrails.")
            
        prompt = f"""你是一个需求分析助手。请将用户输入的旅行需求解析为 JSON 格式。
必须仅输出合法的 JSON，不要包含任何 markdown 标签或说明文字。
JSON 结构如下：
{{
  "city": "城市名",
  "travel_days": 天数(整数),
  "budget": "预算描述",
  "interests": ["兴趣1", "兴趣2"]
}}

用户输入：{state['user_input']}"""
        
        # 针对“普通模型”优化：不使用 with_structured_output，手动解析
        for _ in range(3):
            try:
                res = self.llm.invoke(prompt)
                data = self._extract_json(res.content)
                if data:
                    # 使用 Pydantic 进行校验
                    request = TripRequest(**data)
                    return {"request": request}
            except Exception as e:
                print(f"⚠️ [Analyzer] 重试中... {e}")
        raise ValueError("Failed to parse TripRequest after 3 retries.")

    def decomposer_node(self, state: AgentState):
        """任务拆解 Agent：根据需求制定执行计划"""
        print("📋 [Task Decomposer] 拆解任务步骤...")
        prompt = f"""基于以下结构化需求，拆解出获取信息的步骤。
必须仅输出合法的 JSON，不要包含任何 markdown 标签或说明文字。
结构如下：
{{
  "steps": ["步骤1", "步骤2"],
  "needed_tools": ["工具名1", "工具名2"],
  "potential_risks": ["风险1"]
}}

需求详情：{state['request'].model_dump_json()}"""
        for _ in range(3):
            try:
                res = self.llm.invoke(prompt)
                data = self._extract_json(res.content)
                if data:
                    decomposition = TaskDecomposition(**data)
                    return {"decomposition": decomposition}
            except Exception as e:
                print(f"⚠️ [Decomposer] 重试中... {e}")
        raise ValueError("Failed to decompose task after 3 retries.")

    def weather_expert_node(self, state: AgentState):
        """天气专家 Agent：调用 MCP 获取实时天气"""
        city = state["request"].city
        print(f"🌦️ [Weather Expert] 查询 {city} 天气...")
        res = self._call_tool("maps_weather", {"city": city}, state)
        return {"weather_data": str(res)}

    def poi_expert_node(self, state: AgentState):
        """景点专家 Agent：调用 MCP 获取 POI 信息"""
        city = state["request"].city
        interests = ",".join(state["request"].interests)
        print(f"🏛️ [POI Expert] 在 {city} 搜索 {interests} 相关景点...")
        res = self._call_tool("maps_text_search", {"keywords": interests or "旅游景点", "city": city}, state)
        return {"poi_data": str(res)}

    def route_expert_node(self, state: AgentState):
        """路线专家 Agent：调用 MCP 进行路线规划建议 (简化演示)"""
        print(f"🚗 [Route Expert] 分析城市交通情况...")
        # 实际可以调用 maps_direction 等工具
        return {"route_data": "建议优先选择地铁出行，景区之间打车约 20-30 分钟。"}

    def planner_node(self, state: AgentState):
        """行程规划 Agent：汇总数据生成最终行程单"""
        print("🧠 [Final Planner] 汇总所有数据并生成结构化行程单...")
        context = {
            "request": state["request"].model_dump(),
            "weather": state["weather_data"],
            "poi": state["poi_data"],
            "route": state["route_data"],
            "feedback": state.get("reflection", {}).critique if state.get("reflection") else None
        }
        prompt = f"""请根据以下上下文生成旅行计划。必须仅输出 JSON。
不要包含任何 markdown 标签或说明文字。
JSON 结构如下：
{{
  "city": "上海",
  "summary": "三日美食博物馆之旅",
  "daily_itinerary": [
    {{
      "date_index": 1,
      "theme": "历史文化",
      "activities": [
        {{ "time_slot": "09:00-11:00", "location": "博物馆", "description": "参观展厅", "transport": "打车" }}
      ],
      "meals": {{ "早餐": "酒店", "午餐": "本帮菜", "晚餐": "夜市" }}
    }}
  ],
  "weather_tips": "带伞",
  "total_budget_estimate": "2500元"
}}

上下文：{json.dumps(context, ensure_ascii=False)}"""
        for _ in range(3):
            try:
                res = self.llm.invoke(prompt)
                data = self._extract_json(res.content)
                if data:
                    plan = TripPlan(**data)
                    return {"final_plan": plan}
            except Exception as e:
                print(f"⚠️ [Planner] 重试中... {e}")
        raise ValueError("Failed to generate plan after 3 retries.")

    def critic_node(self, state: AgentState):
        """审计反思 Agent：核查计划合规性与约束满足率"""
        print("⚖️ [Critic Agent] 核查行程合理性...")
        plan_json = state["final_plan"].model_dump_json()
        request_json = state["request"].model_dump_json()
        prompt = f"""请对比需求与行程计划，检查是否满足约束。
必须仅输出合法的 JSON，字段名必须严格匹配：
{{
  "is_valid": true/false,
  "critique": "改进意见",
  "missing_elements": ["缺失项"],
  "retry_needed": true/false
}}
需求：{request_json}
计划：{plan_json}"""
        for _ in range(3):
            try:
                res = self.llm.invoke(prompt)
                data = self._extract_json(res.content)
                if data:
                    reflection = ReflectionResult(**data)
                    # 记录重试次数
                    new_retry_count = state.get("retry_count", 0) + (1 if reflection.retry_needed else 0)
                    if new_retry_count > 3:
                        reflection.retry_needed = False
                        print("⚠️ [Critic] 已达到最大重试次数，强制结束。")
                    return {"reflection": reflection, "retry_count": new_retry_count}
            except Exception as e:
                print(f"⚠️ [Critic] 重试中... {e}")
        raise ValueError("Failed to critique plan after 3 retries.")

    def evaluator_node(self, state: AgentState):
        """评测节点：量化当前行程的全链路效果"""
        print("📊 [Evaluator] 计算全链路评测指标...")
        metrics = TripEvaluator.run_all_evals(state)
        print(f"📈 评测结果: {json.dumps(metrics, ensure_ascii=False)}")
        return {"metrics": metrics}

    def _should_continue(self, state: AgentState):
        """决策函数：判断是否需要重新规划"""
        if state["reflection"].retry_needed:
            print(f"🔄 [Workflow] 计划未通过审计，正在重新规划 (重试次数: {state['retry_count']})...")
            return "planner"
        return "evaluator" # 通过审计后进入评测

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("analyzer", self.analyzer_node)
        workflow.add_node("decomposer", self.decomposer_node)
        workflow.add_node("weather", self.weather_expert_node)
        workflow.add_node("poi", self.poi_expert_node)
        workflow.add_node("route", self.route_expert_node)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("critic", self.critic_node)
        workflow.add_node("evaluator", self.evaluator_node) # 新增

        # 构建连线
        workflow.add_edge(START, "analyzer")
        workflow.add_edge("analyzer", "decomposer")
        workflow.add_edge("decomposer", "weather")
        workflow.add_edge("weather", "poi")
        workflow.add_edge("poi", "route")
        workflow.add_edge("route", "planner")
        workflow.add_edge("planner", "critic")
        
        # 条件路由：反思重规划循环
        workflow.add_conditional_edges(
            "critic",
            self._should_continue,
            {
                "planner": "planner",
                "evaluator": "evaluator" # 审计通过
            }
        )
        workflow.add_edge("evaluator", END) # 评测完结束
        
        return workflow.compile(checkpointer=self.checkpointer)

    def run(self, user_query: str, thread_id: str = "default"):
        """运行入口"""
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "user_input": user_query,
            "retry_count": 0,
            "tool_call_count": 0,
            "history": []
        }
        return self.graph.invoke(initial_state, config=config)
