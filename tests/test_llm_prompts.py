"""LLM 提示词模板离线测试：不依赖网络与 API Key。"""
import os
from pathlib import Path

import pytest

from src.llm import (
    analyze,
    build_messages,
    build_user_prompt,
    find_foreign_decimals,
    find_missing_sections,
    validate_output,
)

SAMPLE_SUMMARY = {
    "match": {
        "match_id": 3773497,
        "date": "2009-05-27",
        "competition": "Champions League",
        "season": "2008/2009",
        "home_team": "Barcelona",
        "away_team": "Manchester United",
        "home_score": 2,
        "away_score": 0,
    },
    "focus_team": "Manchester United",
    "opponent": "Barcelona",
    "team": {
        "goals": 0,
        "shots": 12,
        "shots_on_target": 4,
        "passes": 412,
        "passes_completed": 352,
        "pass_accuracy_pct": 85.4,
        "possessions": 48,
        "possession_share_pct": 41.2,
        "final_third_passes": 96,
        "box_entries": 18,
    },
    "opponent_team": {
        "goals": 2,
        "shots": 14,
        "shots_on_target": 6,
        "passes": 520,
        "passes_completed": 468,
        "pass_accuracy_pct": 90.0,
        "possessions": 52,
        "possession_share_pct": 58.8,
        "final_third_passes": 132,
        "box_entries": 24,
    },
    "style": {
        "formation": "4-4-2",
        "avg_pass_length": 17.3,
        "long_ball_ratio_pct": 10.2,
        "passes_per_possession": 8.6,
        "press_events_opp_third": 7,
    },
    "attack_preference": {
        "left_pct": 36.4,
        "center_pct": 41.0,
        "right_pct": 22.6,
        "crosses": 18,
        "through_balls": 3,
        "avg_shot_distance": 17.8,
        "shots_inside_box": 8,
        "shots_outside_box": 4,
    },
    "core_players": [
        {
            "name": "Nemanja Vidić",
            "score": 12.4,
            "passes": 65,
            "pass_accuracy_pct": 89.2,
            "key_passes": 3,
            "shots": 2,
            "goals": 1,
            "touches": 78,
            "network_degree": 9,
            "duels_won": 5,
            "interceptions": 2,
        }
    ],
    "players": [
        {
            "name": "Nemanja Vidić",
            "passes": 65,
            "pass_accuracy_pct": 89.2,
            "avg_x": 38.4,
            "avg_y": 31.0,
            "shots": 0,
            "goals": 0,
            "key_passes": 1,
        }
    ],
    "shot_list": [
        {
            "minute": 10,
            "player": "Cristiano Ronaldo dos Santos Aveiro",
            "x": 102.3,
            "y": 44.1,
            "outcome": "Saved",
            "is_goal": False,
        }
    ],
}

VALID_OUTPUT = (
    "结论：曼联以 0 比 2 落败，射门 12 次但仅 4 次射正，控球率 41.2%。\n"
    "战术风格：球队传球成功率 85.4%，平均传球距离 17.3 米。\n"
    "进攻偏好：中路进攻占比 41.0%，左路 36.4%，右路 22.6%。\n"
    "核心球员表现：维迪奇触球 78 次，传球成功率 89.2%，评分 12.4。\n"
    "建议：增加禁区内射门，本场禁区内射门仅 8 次。"
)


def test_system_prompt_contains_hard_constraints():
    from src.llm.prompts import SYSTEM_PROMPT

    for keyword in ["只能使用", "禁止引入任何外部知识", "禁止编造", "数据不足", "中文", "800"]:
        assert keyword in SYSTEM_PROMPT
    for title in ["结论", "战术风格", "进攻偏好", "核心球员表现", "建议"]:
        assert title in SYSTEM_PROMPT


def test_build_messages_separates_system_and_user():
    messages = build_messages(SAMPLE_SUMMARY, "分析这支球队的战术风格")
    assert [m["role"] for m in messages] == ["system", "user"]
    system_text = messages[0]["content"]
    user_text = messages[1]["content"]
    # 用户输入不能覆盖 system 约束：system 文本只出现在 system 消息里
    assert "你是足球战术分析师" in system_text
    assert system_text not in user_text
    assert "分析这支球队的战术风格" in user_text
    assert "focus_team" in user_text


def test_build_user_prompt_truncates_to_2000_chars():
    long_prompt = "攻" * 2500
    user_text = build_user_prompt(SAMPLE_SUMMARY, long_prompt)
    # 截断只作用于用户提示词本身：重新定位被截断部分
    marker = "用户分析请求：\n"
    prompt_part = user_text.split(marker, 1)[1]
    assert len(prompt_part) == 2000
    assert prompt_part == "攻" * 2000


def test_validate_output_accepts_valid_sample():
    assert validate_output(VALID_OUTPUT, SAMPLE_SUMMARY) == []


def test_validate_output_flags_missing_section():
    text = VALID_OUTPUT.replace("核心球员表现", "球员表现")
    problems = validate_output(text, SAMPLE_SUMMARY)
    assert any("核心球员表现" in p for p in problems)


def test_validate_output_flags_overlong():
    text = "结论：测试。" * 300
    problems = validate_output(text, SAMPLE_SUMMARY)
    assert any("总字数超限" in p for p in problems)


def test_validate_output_flags_foreign_decimal():
    # 示例 JSON 中没有 xG 字段，模型若编造 2.5 会被检出
    text = VALID_OUTPUT + "\n预期进球：本场 xG 为 2.5。"
    problems = validate_output(text, SAMPLE_SUMMARY)
    assert any("2.5" in p for p in problems)


def test_find_foreign_decimals_rejects_xg():
    assert find_foreign_decimals("xG 为 2.5", SAMPLE_SUMMARY) == ["2.5"]
    assert find_foreign_decimals("传球成功率 85.4%", SAMPLE_SUMMARY) == []


def test_find_missing_sections():
    assert find_missing_sections(VALID_OUTPUT) == []
    assert find_missing_sections("只有结论：0 比 2 落败。") == [
        "战术风格",
        "进攻偏好",
        "核心球员表现",
        "建议",
    ]


def test_analyze_without_key_raises_llm_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.llm.client._ENV_FILE", Path(tmp_path) / "no.env")
    with pytest.raises(Exception) as exc_info:
        analyze(SAMPLE_SUMMARY, "分析战术")
    assert type(exc_info.value).__name__ == "LLMUnavailable"
    assert "OPENAI_API_KEY" in str(exc_info.value)
