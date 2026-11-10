import pytest

from reelbarrow.names import LATIN1_END, UnwritableName, component, fold


def test_providers_dashes_and_quotes_become_latin1():
    assert fold("Tweety (1995\N{EN DASH}2002)") == "Tweety (1995-2002)"
    assert fold("Ocean\N{RIGHT SINGLE QUOTATION MARK}s Eleven") == "Ocean's Eleven"
    assert fold("Wait\N{HORIZONTAL ELLIPSIS}") == "Wait..."


def test_latin1_is_kept_and_the_rest_keeps_its_base_letter():
    # Mànran is in the library under its Latin-1 name.
    assert fold("Mànran") == "Mànran"
    assert fold("Pok\N{LATIN SMALL LETTER E WITH ACUTE}mon") == "Pokémon"
    assert fold("Dvo\N{LATIN SMALL LETTER R WITH CARON}ák") == "Dvorák"
    assert all(ord(c) < LATIN1_END for c in fold("Nausica\N{GREEK SMALL LETTER ALPHA}"))


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
