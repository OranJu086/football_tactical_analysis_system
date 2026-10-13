"""模型接入层：OpenAI 兼容客户端与提示词模板。"""
from .client import LLMUnavailable, analyze
from .prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_MAX_CHARS,
    build_messages,
    build_system_prompt,
    build_user_prompt,
    find_foreign_decimals,
    find_missing_sections,
    validate_output,
)

__all__ = [
    "LLMUnavailable",
    "analyze",
    "SYSTEM_PROMPT",
    "USER_PROMPT_MAX_CHARS",
    "build_messages",
    "build_system_prompt",
    "build_user_prompt",
    "find_foreign_decimals",
    "find_missing_sections",
    "validate_output",
]
