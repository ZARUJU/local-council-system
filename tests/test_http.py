from local_council_system.http_client import canonical_url

BASE = (
    "https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe"
    "?ACT=100&KTYP=0,1,2,3&SORT=0&FYY=2025&KGTP=3&TYY=2025&TITL="
)


def test_canonical_url_keeps_sjis_titl_distinct() -> None:
    water = BASE + "%90%85%93%B9"
    education = BASE + "%95%B6%8B%B3"
    assert canonical_url(water) != canonical_url(education)


def test_canonical_url_normalizes_comma_encoding() -> None:
    comma = "https://example.test/cgi?KGTP=1,2"
    encoded = "https://example.test/cgi?KGTP=1%2C2"
    assert canonical_url(comma) == canonical_url(encoded)
