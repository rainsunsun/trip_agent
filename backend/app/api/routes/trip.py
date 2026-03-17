"""旅行规划 API 路由"""

from fastapi import APIRouter, HTTPException
from ...models.schemas import TripRequest, TripPlanResponse
from ...agents.trip_planner_agent import get_trip_planner_agent

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求生成详细的旅行计划",
)
async def plan_trip(request: TripRequest):
    try:
        print("[api] received trip plan request")
        agent = get_trip_planner_agent()
        trip_plan = agent.plan_trip(request)

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan,
        )
    except Exception as e:
        print(f"[api] failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"旅行计划生成失败: {str(e)}",
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常",
)
async def health_check():
    try:
        agent = get_trip_planner_agent()
        return {
            "status": "healthy",
            "service": "trip-planner",
            "graph_nodes": agent.graph_nodes,
            "graph_nodes_count": len(agent.graph_nodes),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}",
        )
