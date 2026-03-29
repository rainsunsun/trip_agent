from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator

# 1. 用户初始需求模型
class TripRequest(BaseModel):
    city: str = Field(..., description="目的地城市")
    travel_days: int = Field(..., ge=1, le=14, description="旅行天数，限制在1-14天")
    budget: Optional[str] = Field(None, description="预算范围，如：经济、舒适、豪华")
    interests: List[str] = Field(default_factory=list, description="兴趣点，如：美食、历史、自然")

# 2. 任务拆解模型 (Task Decomposition)
class TaskDecomposition(BaseModel):
    steps: List[str] = Field(..., description="拆解后的执行步骤")
    needed_tools: List[str] = Field(..., description="每一步可能需要调用的工具名称")
    potential_risks: List[str] = Field(default_factory=list, description="预判可能遇到的异常或限制")

# 3. 结构化行程单模型 (Core Plan)
class Activity(BaseModel):
    time_slot: str = Field(..., description="时间段，如：09:00-11:00")
    location: str = Field(..., description="具体地点名称")
    description: str = Field(..., description="活动内容描述")
    transport: Optional[str] = Field(None, description="交通方式建议")

class DayPlan(BaseModel):
    date_index: int = Field(..., description="第几天")
    theme: str = Field(..., description="当日主题")
    activities: List[Activity] = Field(..., description="当日活动列表")
    meals: Dict[str, str] = Field(..., description="三餐建议，包含：早餐、午餐、晚餐")

class TripPlan(BaseModel):
    city: str = Field(..., description="城市名称")
    summary: str = Field(..., description="行程概览")
    daily_itinerary: List[DayPlan] = Field(..., description="每日详细行程")
    weather_tips: str = Field(..., description="基于实时的天气穿衣/出行建议")
    total_budget_estimate: str = Field(..., description="预估总开销")

    @field_validator("daily_itinerary")
    @classmethod
    def validate_itinerary(cls, v):
        if not v:
            raise ValueError("Itinerary cannot be empty")
        # 校验天数是否连续
        indices = [d.date_index for d in v]
        if indices != list(range(1, len(v) + 1)):
            raise ValueError("Date indices must be continuous and start from 1")
        return v

# 4. 反思与修正模型 (Reflection)
class ReflectionResult(BaseModel):
    is_valid: bool = Field(..., description="行程是否满足所有约束")
    critique: Optional[str] = Field(None, description="具体的改进意见")
    missing_elements: List[str] = Field(default_factory=list, description="缺失的关键要素")
    retry_needed: bool = Field(default=False, description="是否需要重规划")