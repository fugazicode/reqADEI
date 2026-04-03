"""Human-readable labels and edit metadata for all mandatory fields."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Edit type constants
FREE_TEXT = "free_text"
DROPDOWN = "dropdown"
DATE = "date"


@dataclass(frozen=True)
class FieldMeta:
    label: str
    edit_type: str           # FREE_TEXT | DROPDOWN | DATE
    enum_key: Optional[str] = None  # portal_enums attribute name, for DROPDOWN


# ── Owner fields (mandatory only) ────────────────────────────────────────────
OWNER_FIELDS: dict[str, FieldMeta] = {
    "owner.first_name":                FieldMeta("First Name",            FREE_TEXT),
    "owner.relative_name":             FieldMeta("Relative Name",         FREE_TEXT),
    "owner.relation_type":             FieldMeta("Relation Type",         DROPDOWN, "RELATION_TYPES"),
    "owner.occupation":                FieldMeta("Occupation",            DROPDOWN, "OCCUPATIONS"),
    "owner.address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "owner.address.country":           FieldMeta("Country",               FREE_TEXT),
    "owner.address.state":             FieldMeta("State",                 DROPDOWN, "STATES"),
    "owner.address.district":          FieldMeta("District",              DROPDOWN, "DISTRICTS"),
    "owner.address.police_station":    FieldMeta("Police Station",        DROPDOWN, "STATIONS"),
}

OWNER_MANDATORY = {
    "owner.first_name",
    "owner.relative_name",
    "owner.relation_type",
    "owner.occupation",
    "owner.address.village_town_city",
    "owner.address.country",
    "owner.address.state",
    "owner.address.district",
    "owner.address.police_station",
}

# ── Tenant personal fields (mandatory only) ───────────────────────────────────
TENANT_PERSONAL_FIELDS: dict[str, FieldMeta] = {
    "tenant.first_name":                    FieldMeta("First Name",         FREE_TEXT),
    "tenant.relative_name":                 FieldMeta("Relative Name",      FREE_TEXT),
    "tenant.relation_type":                 FieldMeta("Relation Type",      DROPDOWN, "RELATION_TYPES"),
    "tenant.address_verification_doc_type": FieldMeta("ID Proof Type",      DROPDOWN, "ADDRESS_DOC_TYPES"),
    "tenant.address_verification_doc_no":   FieldMeta("ID Proof No.",       FREE_TEXT),
    "tenant.purpose_of_tenancy":            FieldMeta("Purpose of Tenancy", DROPDOWN, "TENANCY_PURPOSES"),
}

TENANT_PERSONAL_MANDATORY = {
    "tenant.first_name",
    "tenant.relative_name",
    "tenant.relation_type",
    "tenant.address_verification_doc_type",
    "tenant.address_verification_doc_no",
    "tenant.purpose_of_tenancy",
}

# ── Tenant tenanted premises address (always Delhi) ──────────────────────────
TENANTED_ADDR_FIELDS: dict[str, FieldMeta] = {
    "tenant.tenanted_address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "tenant.tenanted_address.district":          FieldMeta("District (Delhi)",       DROPDOWN, "DISTRICTS"),
    "tenant.tenanted_address.police_station":    FieldMeta("Police Station",         DROPDOWN, "STATIONS"),
}

TENANTED_ADDR_MANDATORY = {
    "tenant.tenanted_address.village_town_city",
    "tenant.tenanted_address.district",
    "tenant.tenanted_address.police_station",
}

# ── Tenant permanent address ─────────────────────────────────────────────────
# All 5 address fields are always mandatory regardless of country value.
PERM_ADDR_FIELDS: dict[str, FieldMeta] = {
    "tenant.address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "tenant.address.country":           FieldMeta("Country",               FREE_TEXT),
    "tenant.address.state":             FieldMeta("State",                 DROPDOWN, "STATES"),
    "tenant.address.district":          FieldMeta("District",              DROPDOWN, "DISTRICTS"),
    "tenant.address.police_station":    FieldMeta("Police Station",        DROPDOWN, "STATIONS"),
}

PERM_ADDR_MANDATORY = {
    "tenant.address.village_town_city",
    "tenant.address.country",
    "tenant.address.state",
    "tenant.address.district",
    "tenant.address.police_station",
}
