from shared.portal_enums import OWNER_OCCUPATIONS, TENANCY_PURPOSES


def test_owner_occupation_aliases() -> None:
    assert OWNER_OCCUPATIONS.normalize("PRIVATE SERVICE") == "COMPANY EXECUTIVE"
    assert OWNER_OCCUPATIONS.normalize("PVT SERVICE") == "COMPANY EXECUTIVE"
    assert OWNER_OCCUPATIONS.normalize("BUSINESS") == "BUSINESS"


def test_tenancy_purpose_aliases() -> None:
    assert TENANCY_PURPOSES.normalize("Commercial") == "OFFICE"
    assert TENANCY_PURPOSES.normalize("Residential") == "RESIDENTIAL"
