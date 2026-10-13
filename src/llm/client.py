"""OpenAI 兼容模型接入层。"""
import os
import time
from pathlib import Path

from .prompts import build_messages

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2


class LLMUnavailable(Exception):
    """模型不可用或调用失败时抛出，message 含原始错误信息（已打码）。"""


def _load_dotenv(path: Path) -> None:
    """极简 .env 读取：不覆盖已存在的环境变量，不引入第三方依赖。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _mask_secret(text: str, secret: str) -> str:
    """把 API Key 从任意文本中打码，防止泄露。"""
    if secret:
        text = text.replace(secret, "***")
        text = text.replace(secret.strip(), "***")
    return text


def _settings() -> tuple:
    """读取环境变量配置，返回 (api_key, base_url, model, timeout, max_retries)。"""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        timeout = float(os.environ.get("LLM_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    try:
        max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
    except ValueError:
        max_retries = DEFAULT_MAX_RETRIES
    return api_key, base_url, model, timeout, max_retries


def analyze(summary: dict, user_prompt: str) -> str:
    """输入统计摘要 JSON 与用户提示词，输出中文战术分析文本。"""
    _load_dotenv(_ENV_FILE)
    api_key, base_url, model, timeout, max_retries = _settings()

    if not api_key:
        raise LLMUnavailable("OPENAI_API_KEY 未配置，无法调用模型")

    messages = build_messages(summary, user_prompt)

    deadline = time.monotonic() + timeout
    last_exc = None
    content = None

    try:
        from openai import OpenAI

        # 重试由本函数自管，确保总耗时不超过 LLM_TIMEOUT
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        for attempt in range(max_retries + 1):
            # 预留 0.2s 给超时异常的传播开销，确保在 LLM_TIMEOUT 内抛出
            remaining = deadline - time.monotonic() - 0.2
            if remaining <= 0:
                break
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    timeout=remaining,
                )
                content = response.choices[0].message.content
                break
            except Exception as exc:  # noqa: BLE001 - 记录后按剩余时间决定是否重试
                last_exc = exc
    except LLMUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - 客户端构造等错误同样包装
        last_exc = exc

    if content is not None and content.strip():
        return content.strip()

    masked = _mask_secret(str(last_exc), api_key) if last_exc else "未知错误"
    if time.monotonic() >= deadline:
        raise LLMUnavailable(f"模型调用超时（超过 {timeout} 秒）: {masked}") from last_exc
    if last_exc is not None:
        raise LLMUnavailable(f"模型调用失败: {masked}") from last_exc
    raise LLMUnavailable("模型返回空内容")
