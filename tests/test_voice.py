import pytest

from gesture_cad import config as CFG
from gesture_cad.voice import VoiceMatcher, normalize


@pytest.fixture
def m():
    return VoiceMatcher(CFG.load()["voice"])


def cmd(m, text, listening=True):
    st, c = m.decide(text, listening)
    return st, (c[1] if c else None)


def test_spoken_forms_are_normalized():
    assert normalize("Auto Cad please help me") == "autocad please help me"
    assert normalize("poly line please") == "polyline please"
    assert normalize("three d rotate") == "3d rotate"


def test_sleeping_ignores_everything_but_wake(m):
    assert cmd(m, "line please", listening=False) == (None, None)
    assert cmd(m, "we should cut this budget", listening=False) == (None, None)
    assert cmd(m, "auto cad please help me", listening=False) == ("wake", None)
    assert cmd(m, "auto cad are you ready", listening=False) == ("wake", None)


def test_wake_and_command_in_one_sentence(m):
    assert cmd(m, "auto cad poly line please", listening=False) == ("wake", "POLYLINE")


@pytest.mark.parametrize("said,label", [
    ("line", "LINE"), ("poly line please", "POLYLINE"), ("cut", "TRIM"), ("extend", "EXTEND"),
    ("three d rotate", "3DROTATE"), ("rotate", "ROTATE"), ("zoom extents", "ZOOM EXT"),
    ("please draw a circle", "CIRCLE"), ("enter", "ENTER"), ("cancel", "ESC"), ("press pull", "PRESSPULL"),
])
def test_listening_commands(m, said, label):
    assert cmd(m, said) == (None, label)


def test_sleep_phrase(m):
    assert cmd(m, "thank you") == ("sleep", None)


def test_vocabulary_is_spoken_words_only(m):
    v = m.vocabulary()
    assert "auto" in v and "cad" in v and "poly" in v and "three" in v
    assert "autocad" not in v and "3d" not in v and "polyline" not in v


def test_shipped_voice_commands_have_no_duplicates():
    assert CFG.validate(CFG.load()) == []
