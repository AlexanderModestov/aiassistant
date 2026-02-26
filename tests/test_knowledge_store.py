from knowledge.store import KnowledgeStore


def test_find_rules_matches_keywords():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Use region not district for Краснодар", "keywords": ["краснодар", "край", "регион"]},
        {"id": 2, "rule_text": "КИМ means control measurements", "keywords": ["ким", "контрольн"]},
    ]
    matched = store.find_rules("Сколько работ в Краснодаре?")
    assert len(matched) == 1
    assert matched[0]["id"] == 1


def test_find_rules_no_match():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Some rule", "keywords": ["москва"]},
    ]
    matched = store.find_rules("Результаты по математике")
    assert matched == []


def test_find_rules_case_insensitive():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Rule about KIM", "keywords": ["ким"]},
    ]
    matched = store.find_rules("Сколько КИМ сдано?")
    assert len(matched) == 1


def test_find_rules_multiple_matches():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Rule 1", "keywords": ["математик"]},
        {"id": 2, "rule_text": "Rule 2", "keywords": ["результат"]},
        {"id": 3, "rule_text": "Rule 3", "keywords": ["физика"]},
    ]
    matched = store.find_rules("Средний результат по математике")
    assert len(matched) == 2
    assert {r["id"] for r in matched} == {1, 2}


def test_find_alias_exact_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("школа 5 краснодар")
    assert result is not None
    assert result["canonical_name"] == "МБОУ СОШ №5 г. Краснодар"


def test_find_alias_substring_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("результаты школа 5 краснодар за неделю")
    assert result is not None
    assert result["canonical_name"] == "МБОУ СОШ №5 г. Краснодар"


def test_find_alias_no_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("школа 10 москва")
    assert result is None
