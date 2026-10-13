"""API 请求数据结构（响应体由路由直接构造，不在此定义）。"""
from pydantic import BaseModel, Field, model_validator


class AnalyzeRequest(BaseModel):
    """POST /api/analyze 的请求体。"""

    match_id: int = Field(gt=0, description="比赛 ID，必须是正整数")
    team_name: str = Field(description="分析球队名")
    prompt: str = Field(description="用户提示词")

    @model_validator(mode="before")
    @classmethod
    def _reject_bool_match_id(cls, data):
        """JSON 中的 true/false 不是合法比赛 ID，必须在类型转换前拒绝。"""
        if isinstance(data, dict) and isinstance(data.get("match_id"), bool):
            raise ValueError("match_id 必须是正整数")
        return data
