import pytest

from mentor.textutil import quiz_competency_arg


def test_quiz_competency_arg_empty() -> None:
    assert quiz_competency_arg("/quiz") == ""
    assert quiz_competency_arg("/quiz@MyBot") == ""


def test_quiz_competency_arg_with_topic() -> None:
    assert quiz_competency_arg("/quiz ml-metrics") == "ml-metrics"
    assert quiz_competency_arg("/quiz@Bot ml-foundations") == "ml-foundations"


def test_quiz_competency_arg_not_quiz() -> None:
    with pytest.raises(ValueError):
        quiz_competency_arg("/help")
