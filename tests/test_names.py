import pytest

from reelbarrow.names import ASCII_END, UnwritableName, component, fold


def test_providers_dashes_and_quotes_become_ascii():
    assert fold("Tweety (1995\N{EN DASH}2002)") == "Tweety (1995-2002)"
    assert fold("Ocean\N{RIGHT SINGLE QUOTATION MARK}s Eleven") == "Ocean's Eleven"
    assert fold("Wait\N{HORIZONTAL ELLIPSIS}") == "Wait..."
    assert fold("A\N{NO-BREAK SPACE}B") == "A B"


def test_an_accented_letter_keeps_its_base():
    assert fold("Am\N{LATIN SMALL LETTER E WITH ACUTE}lie") == "Amelie"
    assert fold("M\N{LATIN SMALL LETTER A WITH GRAVE}nran") == "Manran"
    assert fold(
        "Dvo\N{LATIN SMALL LETTER R WITH CARON}\N{LATIN SMALL LETTER A WITH ACUTE}k"
    ) == ("Dvorak")


def test_a_letter_with_no_base_is_spelled_out_not_lost():
    assert fold("\N{LATIN CAPITAL LETTER AE}on Flux") == "AEon Flux"
    assert fold("Stra\N{LATIN SMALL LETTER SHARP S}e") == "Strasse"
    assert fold(
        "Sm\N{LATIN SMALL LETTER O WITH STROKE}rrebr\N{LATIN SMALL LETTER O WITH STROKE}d"
    ) == ("Smorrebrod")


def test_nothing_above_ascii_survives():
    for text in (
        "Nausica\N{GREEK SMALL LETTER ALPHA}",
        "\N{SNOWMAN} Day",
        "Pok\N{LATIN SMALL LETTER E WITH ACUTE}mon",
    ):
        assert all(ord(c) < ASCII_END for c in fold(text))


def test_a_colon_is_written_as_the_library_writes_it():
    # As the 2024 entries were filed: `Thor - Ragnarok (2017) {tmdb-284053}`.
    assert fold("Thor: Ragnarok") == "Thor - Ragnarok"
    assert fold("2:22") == "2-22"


def test_characters_windows_clients_refuse_are_replaced_or_dropped():
    assert fold('What? "Me" <worry>|*') == "What 'Me' worry"
    assert fold("AC/DC: Live\\Loud") == "AC-DC - Live-Loud"


def test_a_component_drops_a_trailing_dot_or_space():
    assert component("Mr. Smith Goes to Washington.") == "Mr. Smith Goes to Washington"
    assert component("  spaced   out  ") == "spaced out"


@pytest.mark.parametrize("name", ["???", "...", "\N{SNOWMAN}", ""])
def test_a_name_with_nothing_writable_is_refused(name):
    with pytest.raises(UnwritableName):
        component(name)


def test_a_name_longer_than_the_share_allows_is_refused():
    with pytest.raises(UnwritableName):
        component("x" * 256)
    assert component("x" * 255)
