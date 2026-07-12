import pytest

from mentor.textutil import (
    parse_new_topic_arg,
    parse_question_id_arg,
    parse_quiz_args,
    parse_search_query,
    parse_topic_arg,
    quiz_competency_arg,
    reset_is_confirmed,
)


def test_quiz_competency_arg_empty() -> None:
    assert quiz_competency_arg("/quiz") == ""
    assert quiz_competency_arg("/quiz@MyBot") == ""


def test_quiz_competency_arg_with_topic() -> None:
    assert quiz_competency_arg("/quiz ml-metrics") == "ml-metrics"
    assert quiz_competency_arg("/quiz@Bot ml-foundations") == "ml-foundations"


def test_parse_quiz_args_difficulty_only() -> None:
    assert parse_quiz_args("/quiz 2") == ("", 2)
    assert parse_quiz_args("/quiz hard") == ("", 3)


def test_parse_quiz_args_topic_and_difficulty() -> None:
    comp, diff = parse_quiz_args(
        "/quiz ml-metrics 2",
        valid_competency_ids={"ml-metrics", "other"},
    )
    assert comp == "ml-metrics"
    assert diff == 2


def test_quiz_competency_arg_not_quiz() -> None:
    with pytest.raises(ValueError):
        quiz_competency_arg("/help")


def test_parse_search_query() -> None:
    assert parse_search_query("/search precision") == "precision"
    assert parse_search_query("/search") == ""
    assert parse_search_query("/find recall") == "recall"


def test_parse_topic_arg() -> None:
    assert parse_topic_arg("/topic ml-metrics") == "ml-metrics"
    assert parse_topic_arg("/topic") == ""


def test_parse_question_id_with_id_alias() -> None:
    assert parse_question_id_arg("/id ml-001") == "ml-001"


def test_parse_new_topic_arg_unseen() -> None:
    assert parse_new_topic_arg("/unseen ml-metrics") == "ml-metrics"


def test_parse_question_id_open_alias() -> None:
    assert parse_question_id_arg("/open ml-001") == "ml-001"


def test_parse_new_topic_arg() -> None:
    assert parse_new_topic_arg("/new") == ""
    assert parse_new_topic_arg("/new ml-metrics") == "ml-metrics"


def test_parse_question_id_arg() -> None:
    assert parse_question_id_arg("/question ml-001") == "ml-001"
    assert parse_question_id_arg("/q@Bot py-010") == "py-010"


def test_reset_is_confirmed() -> None:
    assert reset_is_confirmed("/reset") is False
    assert reset_is_confirmed("/reset confirm") is True
    assert reset_is_confirmed("/reset да") is True
