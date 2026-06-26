from mentor import quiz as qz
from mentor.competencies import Competency, format_bank_summary, format_search_results


def test_search_questions_finds_by_prompt() -> None:
    qs = [
        qz.Question(id="1", prompt="What is precision?", answer="p"),
        qz.Question(id="2", prompt="Recall definition", answer="r"),
    ]
    found = qz.search_questions(qs, "precision")
    assert len(found) == 1
    assert found[0].id == "1"


def test_search_questions_multi_token() -> None:
    qs = [
        qz.Question(
            id="1",
            prompt="cross validation k fold",
            answer="cv",
        ),
    ]
    assert qz.search_questions(qs, "cross validation")
    assert not qz.search_questions(qs, "cross precision")


def test_search_questions_finds_by_id() -> None:
    qs = [
        qz.Question(id="ml-024", prompt="Other", answer="x"),
    ]
    assert qz.search_questions(qs, "ml-024")


def test_search_questions_finds_by_competency_id() -> None:
    qs = [
        qz.Question(
            id="1",
            prompt="Other",
            answer="x",
            competency_id="ml-metrics",
        ),
    ]
    assert qz.search_questions(qs, "ml-metrics")


def test_search_questions_finds_by_competency_title() -> None:
    qs = [
        qz.Question(
            id="1",
            prompt="Other",
            answer="x",
            competency_id="ml-metrics",
        ),
    ]
    titles = {"ml-metrics": "Метрики классификации"}
    assert qz.search_questions(qs, "метрики", competency_titles=titles)


def test_search_questions_finds_by_competency_description() -> None:
    qs = [
        qz.Question(
            id="1",
            prompt="Other",
            answer="x",
            competency_id="ml-validation",
        ),
    ]
    descs = {"ml-validation": "кросс валидация train val test"}
    assert qz.search_questions(qs, "кросс", competency_descriptions=descs)


def test_format_bank_summary() -> None:
    comps = [Competency(id="a", title="A", description="")]
    text = format_bank_summary(
        total=10,
        diff_counts={1: 4, 3: 2},
        competencies=comps,
        bank_counts={"a": 10},
    )
    assert "Банк вопросов: 10" in text
    assert "/search" in text


def test_format_search_results_empty_query() -> None:
    assert "Укажи слово" in format_search_results([], "")
