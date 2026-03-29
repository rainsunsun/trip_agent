from typing import Dict, Any, List
from ..models.schemas import TripPlan, TripRequest

class TripEvaluator:
    """自动化评测体系：量化行程质量"""

    @staticmethod
    def evaluate_constraint_satisfaction(request: TripRequest, plan: TripPlan) -> float:
        """核心指标 1: 需求约束满足率 (0.0-1.0)"""
        score = 0.0
        total_checks = 0
        
        # 1. 城市匹配度
        total_checks += 1
        if request.city in plan.city:
            score += 1.0
            
        # 2. 天数匹配度
        total_checks += 1
        if len(plan.daily_itinerary) == request.travel_days:
            score += 1.0
        elif abs(len(plan.daily_itinerary) - request.travel_days) == 1:
            score += 0.5 # 容错
            
        # 3. 兴趣覆盖度
        if request.interests:
            total_checks += 1
            interest_count = 0
            for interest in request.interests:
                if any(interest in activity.description for day in plan.daily_itinerary for activity in day.activities):
                    interest_count += 1
            score += interest_count / len(request.interests)
            
        # 4. 结构化程度 (三餐、时间段)
        total_checks += 1
        meal_score = 0
        for day in plan.daily_itinerary:
            if all(k in day.meals and day.meals[k] for k in ["早餐", "午餐", "晚餐"]):
                meal_score += 1
        score += meal_score / len(plan.daily_itinerary)
        
        return score / total_checks

    @staticmethod
    def calculate_task_completion_rate(state: Dict[str, Any]) -> float:
        """核心指标 2: 核心任务完成率"""
        required_keys = ["request", "decomposition", "weather_data", "poi_data", "final_plan"]
        completed = sum(1 for k in required_keys if state.get(k))
        return completed / len(required_keys)

    @staticmethod
    def run_all_evals(state: Dict[str, Any]) -> Dict[str, float]:
        """运行所有评测"""
        results = {}
        if state.get("request") and state.get("final_plan"):
            results["constraint_satisfaction"] = TripEvaluator.evaluate_constraint_satisfaction(
                state["request"], state["final_plan"]
            )
        
        results["task_completion"] = TripEvaluator.calculate_task_completion_rate(state)
        return results
