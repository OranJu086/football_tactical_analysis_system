"""球队名模糊匹配的离线单元测试：全部用合成索引，不读缓存、不联网。"""
import pytest

from app.team_matcher import (
    SCORE_ALIAS,
    SUGGEST_SCORE_MIN,
    TeamCatalog,
    is_variant_name,
    normalize_name,
    score_candidate,
)


def _build_index(matches):
    """把 (主队, 客队) 列表转成 download_match 维护的比赛索引结构。"""
    return {
        str(number + 1): {'home': home, 'away': away}
        for number, (home, away) in enumerate(matches)
    }


def _catalog(matches):
    """按比赛列表构建球队目录。"""
    return TeamCatalog(_build_index(matches))


@pytest.fixture
def catalog():
    """覆盖几种典型写法：带重音的队名、女足同名队、多词队名。"""
    return _catalog(
        [
            ('Barcelona', 'Getafe'),
            ('Barcelona', 'Sevilla'),
            ('Barcelona WFC', 'Sevilla WFC'),
            ('Atlético Madrid', 'Real Sociedad'),
            ('Manchester United', 'Liverpool'),
            ('Manchester United W', 'Liverpool WFC'),
        ]
    )


def test_normalize_name_strips_accents_case_and_punctuation():
    assert normalize_name('Atlético Madrid') == 'atletico madrid'
    assert normalize_name('Brighton & Hove Albion') == 'brighton hove albion'
    assert normalize_name('  Real   Madrid ') == 'real madrid'
    assert normalize_name('') == ''


def test_is_variant_name_recognizes_womens_suffixes():
    assert is_variant_name('liverpool wfc')
    assert is_variant_name('manchester united w')
    assert is_variant_name("united states women s")
    assert not is_variant_name('liverpool')


def test_exact_match_ignores_accents_and_returns_canonical_name(catalog):
    result = catalog.resolve('Atletico Madrid')

    assert result.matched_by == 'exact'
    assert result.name == 'Atlético Madrid'


def test_exact_match_is_not_penalized_for_womens_team(catalog):
    result = catalog.resolve('Manchester United W')

    assert result.matched_by == 'exact'
    assert result.name == 'Manchester United W'


def test_alias_resolves_nickname(catalog):
    result = catalog.resolve('barca')

    assert result.matched_by == 'alias'
    assert result.name == 'Barcelona'
    assert result.candidates[0].score == SCORE_ALIAS


def test_prefix_match_resolves_to_plain_club_not_womens_team(catalog):
    result = catalog.resolve('barce')

    assert result.matched_by == 'fuzzy'
    assert result.name == 'Barcelona'


def test_ambiguous_prefix_returns_candidates_without_picking_a_team():
    catalog = _catalog([('Real Madrid', 'Getafe'), ('Real Sociedad', 'Getafe')])
    result = catalog.resolve('real')

    assert result.name is None
    assert result.matched_by == 'ambiguous'
    assert [item.name for item in result.candidates] == ['Real Madrid', 'Real Sociedad']


def test_typo_is_only_offered_as_suggestion(catalog):
    result = catalog.resolve('barcelna')

    assert result.name is None
    assert result.matched_by == 'ambiguous'
    assert result.candidates[0].name == 'Barcelona'
    assert result.candidates[0].score >= SUGGEST_SCORE_MIN


def test_unknown_team_returns_nothing(catalog):
    result = catalog.resolve('xyzzy')

    assert result.name is None
    assert result.matched_by == 'none'
    assert result.candidates == []


def test_search_prefers_more_played_team_when_scores_tie():
    catalog = _catalog([('Sevilla', 'Getafe'), ('Sevilla', 'Getafe'), ('Sevilla Atletico', 'Getafe')])
    names = [item.name for item in catalog.search('sevi')]

    assert names == ['Sevilla', 'Sevilla Atletico']


def test_variant_penalty_lowers_score_but_keeps_candidate(catalog):
    plain = score_candidate('liver', 'liverpool')
    variant = score_candidate('liver', 'liverpool wfc')

    assert plain > variant >= SUGGEST_SCORE_MIN


def test_empty_query_returns_popular_teams():
    catalog = _catalog([('A Team', 'B Team'), ('A Team', 'B Team'), ('A Team', 'C Team')])
    names = [item.name for item in catalog.search('')]

    assert names == ['A Team', 'B Team', 'C Team']


def test_broken_index_entries_are_skipped():
    index = {'1': {'home': 'Barcelona', 'away': 'Getafe'}, '2': None, '3': {'home': '', 'away': None}}
    catalog = TeamCatalog(index)

    assert catalog.team_count == 2
    assert catalog.resolve('Barcelona').name == 'Barcelona'
