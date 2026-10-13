"""球队名归一化与模糊匹配。

比赛索引里的队名是 StatsBomb 的原始写法（带重音、带 Women / WFC 等后缀），
而用户在页面上往往只输入简称（barca）或拼错的写法（barcelna）。
这里负责把这类输入对应到索引中的规范队名，供自动补全与比赛查询使用。

相关度分数（越高越可信）：
    100  归一化后完全一致（Atletico Madrid → Atlético Madrid）
     96  命中别名表（barca → Barcelona）
     90  整名前缀（barce → Barcelona）
     84  队名中某个词的前缀（united → Manchester United）
     78  多词查询，每个词都对上队名中某个词的前缀（man united → Manchester United）
     74  子串出现（celona → Barcelona）
  45~60  编辑距离相似度，给拼写错误的输入兜底

只有分数达到 DECISIVE_SCORE_MIN 且明显领先第二名的候选才会被自动采用，
否则只作为候选项交给前端展示，不在多支球队之间乱猜。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

# 低于该分数不算相关，不进入候选列表
SUGGEST_SCORE_MIN = 45.0

# 可以被自动采用的候选的最低分数
DECISIVE_SCORE_MIN = 74.0

# 自动采用时，第一名需要领先第二名的最小分差
DECISIVE_SCORE_GAP = 12.0

# 允许用编辑距离纠错的最短输入长度（输入太短时相似度没有参考价值）
FUZZY_MIN_LEN = 3

# 编辑距离相似度下限，以及该相似度折算出的最高分
RATIO_MIN = 0.75
RATIO_SCORE_MAX = 60.0

# 各档匹配方式的固定分数
SCORE_EXACT = 100.0
SCORE_ALIAS = 96.0
SCORE_PREFIX = 90.0
SCORE_WORD_PREFIX = 84.0
SCORE_MULTI_WORD = 78.0
SCORE_SUBSTRING = 74.0

# 女足、预备队等后缀标记：同一家俱乐部在索引里往往既有 'Liverpool' 也有
# 'Liverpool WFC'。用户只输入俱乐部名前缀（barce、liver）时，
# 应当让不带后缀的那个排在前面，而不是把两者都当成歧义候选。
VARIANT_TOKENS = {'w', 'wfc', 'fcw', 'lfc', 'women', 'womens', 'ladies'}

# 带后缀队名的降权分数：足够拉开一个档次，但不至于把它们挤出候选列表
VARIANT_PENALTY = 12.0

# 常见简称与俗称 → 索引中的规范队名。
# 键在比对前会做同样的归一化，所以这里可以按平时的写法写；
# 目标队名不在索引里时该条自动失效，不需要在这里维护索引里有哪些队。
TEAM_ALIASES = {
    'barca': 'Barcelona',
    'man utd': 'Manchester United',
    'man united': 'Manchester United',
    'manchester utd': 'Manchester United',
    'man city': 'Manchester City',
    'atleti': 'Atlético Madrid',
    'psg': 'Paris Saint-Germain',
    'juve': 'Juventus',
    'spurs': 'Tottenham Hotspur',
    'bayern': 'Bayern Munich',
    'bvb': 'Borussia Dortmund',
    'dortmund': 'Borussia Dortmund',
}


def normalize_name(name):
    """把队名归一化成便于比较的形式：去重音、转小写、标点转空格、压缩空白。

    例：'Atlético Madrid' → 'atletico madrid'；'Brighton & Hove Albion' → 'brighton hove albion'。
    """
    text = unicodedata.normalize('NFKD', str(name or ''))
    # 去掉附加符号：Á → A、ñ → n、ç → c
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    # 标点、& 等非字母数字字符统一变成空格，再压缩连续空格
    text = re.sub(r'[^a-z0-9]+', ' ', text.lower())
    return ' '.join(text.split())


def score_with_penalty(score, team_norm):
    """带后缀队名降权：分数先减去降权值，最低不低于 0。"""
    if is_variant_name(team_norm):
        return max(score - VARIANT_PENALTY, 0.0)
    return score


def is_variant_name(team_norm):
    """队名是否带女足、预备队之类的后缀标记（Liverpool WFC、Chelsea FCW）。"""
    return bool(set(team_norm.split()) & VARIANT_TOKENS)


def score_candidate(query_norm, team_norm):
    """给「归一化后的输入」与「归一化后的队名」打分，返回 0.0 表示不相关。

    完全一致（100 分）的分数不会被后缀降权影响，用户写全名时永远命中写全名的那支队。
    """
    if not query_norm or not team_norm:
        return 0.0

    if query_norm == team_norm:
        return SCORE_EXACT

    team_words = team_norm.split()

    # 整名前缀：barce → barcelona
    if team_norm.startswith(query_norm):
        return score_with_penalty(SCORE_PREFIX, team_norm)

    # 队名中某个词的前缀：united → manchester united
    if any(word.startswith(query_norm) for word in team_words):
        return score_with_penalty(SCORE_WORD_PREFIX, team_norm)

    # 多词查询：每个词都能对上队名中某个词的前缀（man united → manchester united）
    query_words = query_norm.split()
    if len(query_words) > 1:
        if all(any(word.startswith(part) for word in team_words) for part in query_words):
            return score_with_penalty(SCORE_MULTI_WORD, team_norm)

    # 子串出现：celona → barcelona
    if query_norm in team_norm:
        return score_with_penalty(SCORE_SUBSTRING, team_norm)

    # 编辑距离兜底，处理拼写错误：barcelna → barcelona
    if len(query_norm) < FUZZY_MIN_LEN:
        return 0.0

    ratio = SequenceMatcher(None, query_norm, team_norm).ratio()
    if ratio < RATIO_MIN:
        return 0.0

    return score_with_penalty(round(RATIO_SCORE_MAX * ratio, 1), team_norm)


@dataclass
class TeamCandidate:
    """一个候选队名：规范队名、索引中的比赛场数、相关度分数。"""

    name: str
    matches: int
    score: float


@dataclass
class TeamResolution:
    """一次用户输入的解析结果。

    name       —— 推荐采用的规范队名（前端回填输入框、接口校验都用它），无法确定时为 None
    names      —— 归一化后与输入等价的全部规范队名，过滤比赛时用（可能不止一个，例如重名写法）
    matched_by —— exact / alias / fuzzy / ambiguous / none
    candidates —— 按相关度排序的候选列表，供前端做「你是不是要找」提示
    """

    name: str | None
    names: list[str]
    matched_by: str
    candidates: list[TeamCandidate]


class TeamCatalog:
    """由比赛索引构建的球队目录，提供模糊搜索与队名解析。

    index 是 data/match_index.json 的原始内容：{match_id: {home, away, ...}}。
    """

    def __init__(self, index):
        # 规范队名 → 比赛场数
        self._counts = {}
        # 归一化队名 → 规范队名列表（不同写法可能归一化成同一个键）
        self._names_by_norm = {}
        # 归一化简称 → 规范队名（只保留索引里确实存在的目标）
        self._aliases = {}

        for info in index.values():
            if not isinstance(info, dict):
                continue
            for key in ('home', 'away'):
                name = str(info.get(key) or '').strip()
                if name:
                    self._counts[name] = self._counts.get(name, 0) + 1

        for name in self._counts:
            self._names_by_norm.setdefault(normalize_name(name), []).append(name)

        for alias, target in TEAM_ALIASES.items():
            if target in self._counts:
                self._aliases[normalize_name(alias)] = target

    @property
    def team_count(self):
        """索引中的球队总数。"""
        return len(self._counts)

    def popular(self, limit=8):
        """热门球队：按比赛场数降序，场数相同时按队名排序。"""
        names = sorted(self._counts, key=lambda item: (-self._counts[item], item))
        return [TeamCandidate(name, self._counts[name], 0.0) for name in names[:limit]]

    def search(self, query, limit=8):
        """模糊搜索队名，返回按相关度排序的候选；query 为空时返回热门球队。"""
        norm = normalize_name(query)
        if not norm:
            return self.popular(limit)

        alias_target = self._aliases.get(norm)
        candidates = []

        for team_norm, names in self._names_by_norm.items():
            score = score_candidate(norm, team_norm)

            # 命中别名时按别名分数处理，其余匹配方式照常参与比较
            if alias_target is not None and alias_target in names:
                score = max(score, SCORE_ALIAS)

            if score < SUGGEST_SCORE_MIN:
                continue

            # 同一组归一化名只保留场数最多的那个作为代表
            best = max(names, key=lambda item: (self._counts.get(item, 0), item))
            candidates.append(TeamCandidate(best, self._counts.get(best, 0), score))

        # 分数相同的按场数多的优先，让热门球队排在前面
        candidates.sort(key=lambda item: (-item.score, -item.matches, item.name))
        return candidates[:limit]

    def resolve(self, query):
        """解析用户输入：能确定就给出规范队名，候选势均力敌时返回 ambiguous。"""
        norm = normalize_name(query)
        if not norm:
            return TeamResolution(None, [], 'none', self.popular(8))

        candidates = self.search(norm)

        # 1) 与索引里的队名完全一致（只差重音、大小写、标点也算）
        group = self._names_by_norm.get(norm)
        if group:
            best = max(group, key=lambda item: (self._counts.get(item, 0), item))
            return TeamResolution(best, group, 'exact', candidates)

        # 2) 命中别名表
        if norm in self._aliases:
            name = self._aliases[norm]
            return TeamResolution(name, [name], 'alias', candidates)

        # 3) 只有一个候选明显胜出时才自动采用
        if candidates:
            top = candidates[0]
            runner_up = candidates[1].score if len(candidates) > 1 else 0.0
            if top.score >= DECISIVE_SCORE_MIN and top.score - runner_up >= DECISIVE_SCORE_GAP:
                return TeamResolution(top.name, [top.name], 'fuzzy', candidates)

        return TeamResolution(None, [], 'ambiguous' if candidates else 'none', candidates)
