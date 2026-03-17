"""Multi-agent trip planner powered by LangGraph."""

import json
from typing import Dict, Any, List, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from hello_agents.tools import MCPTool

from ..services.llm_service import get_llm
from ..models.schemas import TripRequest, TripPlan, DayPlan, Attraction, Meal, WeatherInfo, Location, Hotel
from ..config import get_settings


PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息生成详细的旅行计划。

请严格按以下 JSON 格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

重要提示:
1. weather_info 数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带单位)
3. 每天安排 2-3 个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. 必须包含预算信息
"""


class TripPlannerState(TypedDict, total=False):
    request: TripRequest
    attractions: str
    weather: str
    hotels: str
    plan_text: str


class MultiAgentTripPlanner:
    """Multi-agent trip planner built with LangGraph."""

    def __init__(self) -> None:
        print("[init] building LangGraph trip planner...")
        settings = get_settings()
        self.llm = get_llm()

        self.amap_tool = MCPTool(
            name="amap",
            description="Gaode Maps MCP service",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=True,
        )

        self.graph = self._build_graph()
        self.graph_nodes = ["attraction", "weather", "hotel", "planner"]
        print("[init] graph ready")

    def _build_graph(self):
        graph = StateGraph(TripPlannerState)
        graph.add_node("attraction", self._attraction_node)
        graph.add_node("weather", self._weather_node)
        graph.add_node("hotel", self._hotel_node)
        graph.add_node("planner", self._planner_node)

        graph.add_edge(START, "attraction")
        graph.add_edge("attraction", "weather")
        graph.add_edge("weather", "hotel")
        graph.add_edge("hotel", "planner")
        graph.add_edge("planner", END)

        return graph.compile()

    def plan_trip(self, request: TripRequest) -> TripPlan:
        try:
            print("[plan] start planning")
            state = self.graph.invoke({"request": request})
            plan_text = state.get("plan_text", "")
            trip_plan = self._parse_response(plan_text, request)
            print("[plan] done")
            return trip_plan
        except Exception as e:
            print(f"[plan] failed: {e}")
            return self._create_fallback_plan(request)

    def _call_amap_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        try:
            return self.amap_tool.run(
                {
                    "action": "call_tool",
                    "tool_name": tool_name,
                    "arguments": arguments,
                }
            )
        except Exception as e:
            print(f"[tool] {tool_name} failed: {e}")
            return ""

    def _attraction_node(self, state: TripPlannerState) -> Dict[str, Any]:
        request = state["request"]
        keywords = request.preferences[0] if request.preferences else "景点"
        result = self._call_amap_tool(
            "maps_text_search",
            {"keywords": keywords, "city": request.city},
        )
        return {"attractions": result}

    def _weather_node(self, state: TripPlannerState) -> Dict[str, Any]:
        request = state["request"]
        result = self._call_amap_tool("maps_weather", {"city": request.city})
        return {"weather": result}

    def _hotel_node(self, state: TripPlannerState) -> Dict[str, Any]:
        request = state["request"]
        keywords = request.accommodation or "酒店"
        if "酒店" not in keywords and "宾馆" not in keywords:
            keywords = f"{keywords}酒店"
        result = self._call_amap_tool(
            "maps_text_search",
            {"keywords": keywords, "city": request.city},
        )
        return {"hotels": result}

    def _planner_node(self, state: TripPlannerState) -> Dict[str, Any]:
        request = state["request"]
        attractions = state.get("attractions", "")
        weather = state.get("weather", "")
        hotels = state.get("hotels", "")

        planner_query = self._build_planner_query(request, attractions, weather, hotels)
        response = self._invoke_llm(PLANNER_AGENT_PROMPT, planner_query)
        return {"plan_text": response}

    def _invoke_llm(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
        result = self.llm.invoke(messages)
        return getattr(result, "content", str(result))

    def _build_planner_query(
        self,
        request: TripRequest,
        attractions: str,
        weather: str,
        hotels: str = "",
    ) -> str:
        query = f"""请根据以下信息生成 {request.city} 的 {request.travel_days} 天游旅行计划。

基础信息:
- 城市: {request.city}
- 日期: {request.start_date} 到 {request.end_date}
- 天数: {request.travel_days}
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

景点信息:
{attractions}

天气信息:
{weather}

酒店信息:
{hotels}

要求:
1. 每天安排 2-3 个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
4. 考虑景点之间的距离和交通方式
5. 返回完整的 JSON 格式数据
6. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n额外要求: {request.free_text_input}"
        return query

    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        try:
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("response does not include JSON")

            data = json.loads(json_str)
            return TripPlan(**data)
        except Exception as e:
            print(f"[parse] failed: {e}")
            return self._create_fallback_plan(request)

    def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
        from datetime import datetime, timedelta

        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        days: List[DayPlan] = []
        for i in range(request.travel_days):
            current_date = start_date + timedelta(days=i)
            day_plan = DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i+1}天行程",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=[
                    Attraction(
                        name=f"{request.city}景点{j+1}",
                        address=f"{request.city}市",
                        location=Location(
                            longitude=116.4 + i * 0.01 + j * 0.005,
                            latitude=39.9 + i * 0.01 + j * 0.005,
                        ),
                        visit_duration=120,
                        description=f"这是{request.city}的著名景点",
                        category="景点",
                    )
                    for j in range(2)
                ],
                meals=[
                    Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐"),
                    Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐"),
                    Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐"),
                ],
            )
            days.append(day_plan)

        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=[],
            overall_suggestions=f"这是为您规划的 {request.city} {request.travel_days} 天游行程,建议提前查看各景点的开放时间",
        )


_multi_agent_planner: Optional[MultiAgentTripPlanner] = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    global _multi_agent_planner
    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()
    return _multi_agent_planner
