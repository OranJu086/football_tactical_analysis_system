"""提示词模板与输出结构校验逻辑。"""
import json
import re

# 五段结构标题（顺序固定）
SECTION_TITLES = ["结论", "战术风格", "进攻偏好", "核心球员表现", "建议"]

# 用户提示词最大长度（字符）
USER_PROMPT_MAX_CHARS = 2000

SYSTEM_PROMPT = (
    "你是足球战术分析师。你只能使用用户提供的 summary JSON 中的数字进行分析，"
    "禁止引入任何外部知识，禁止编造、推测或补充 JSON 中不存在的数据。"
    "如果用户询问的指标（如 xG、预期进球）在 JSON 中不存在，必须明确回答“数据不足”，"
    "并说明 JSON 中没有该字段，绝不能编造数字。"
    "你必须使用中文输出，并严格按以下五段结构撰写，每段以标题“结论”“战术风格”"
    "“进攻偏好”“核心球员表现”“建议”开头。"
    "每一段中引用的任何数字必须与 JSON 中的数字完全一致。"
    "全文总字数不得超过 800 字。"
)


def build_system_prompt() -> str:
    """返回 system 提示词。"""
    return SYSTEM_PROMPT


def build_user_prompt(summary: dict, user_prompt: str) -> str:
    """把摘要 JSON 与用户提示词组装成 user 消息，用户提示词截断到 2000 字符。"""
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    prompt = (user_prompt or "").strip()
    if len(prompt) > USER_PROMPT_MAX_CHARS:
        prompt = prompt[:USER_PROMPT_MAX_CHARS]
    return f"以下是本场比赛的统计摘要 JSON：\n{payload}\n\n用户分析请求：\n{prompt}"


def build_messages(summary: dict, user_prompt: str) -> list:
    """构造 messages：system 与 user 分离，用户输入不可能覆盖 system 约束。"""
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": build_user_prompt(summary, user_prompt)},
    ]


def _collect_numbers(obj, acc: set):
    """递归收集 JSON 中出现的所有数字（int 与 float 统一按浮点比较）。"""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_numbers(value, acc)
    elif isinstance(obj, list):
        for value in obj:
            _collect_numbers(value, acc)


def find_missing_sections(text: str) -> list:
    """返回缺失的五段标题。"""
    return [title for title in SECTION_TITLES if title not in (text or "")]


def find_foreign_decimals(text: str, summary: dict) -> list:
    """返回输出文本中出现、但 JSON 中不存在的小数 token（用于防幻觉校验）。

    只校验带小数点的数字，避免把日期、段号等整数误判为违规。
    """
    allowed = set()
    _collect_numbers(summary, allowed)
    foreign = []
    for token in re.findall(r"\d+\.\d+", text or ""):
        value = float(token)
        if not any(abs(value - item) < 1e-9 for item in allowed):
            foreign.append(token)
    return foreign


def validate_output(text: str, summary: dict) -> list:
    """校验模型输出，返回问题列表；空列表表示通过。

    覆盖：五段结构完整性、字数上限、小数与 JSON 的一致性。
    """
    problems = []
    problems.extend(f"缺少段落标题：{title}" for title in find_missing_sections(text))
    if len((text or "").strip()) > 800:
        problems.append(f"总字数超限：{len((text or '').strip())} > 800")
    for token in find_foreign_decimals(text, summary):
        problems.append(f"出现 JSON 中不存在的小数：{token}")
    return problems
