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


# ── Owner fields ─────────────────────────────────────────────────────────────
OWNER_FIELDS: dict[str, FieldMeta] = {
    "owner.first_name": FieldMeta("First Name", FREE_TEXT),
    "owner.middle_name": FieldMeta("Middle Name", FREE_TEXT),
    "owner.last_name": FieldMeta("Last Name", FREE_TEXT),
    "owner.relative_name": FieldMeta("Relative Name", FREE_TEXT),
    "owner.relation_type": FieldMeta("Relation Type", DROPDOWN, "RELATION_TYPES"),
    "owner.dob": FieldMeta("Date of Birth", DATE),
    "owner.mobile_no": FieldMeta("Mobile No.", FREE_TEXT),
    "owner.address_verification_doc_no": FieldMeta("Aadhaar No.", FREE_TEXT),
    "owner.occupation": FieldMeta("Occupation", DROPDOWN, "OCCUPATIONS"),
    "owner.address.house_no": FieldMeta("House No.", FREE_TEXT),
    "owner.address.street_name": FieldMeta("Street Name", FREE_TEXT),
    "owner.address.colony_locality_area": FieldMeta("Colony / Locality", FREE_TEXT),
    "owner.address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "owner.address.tehsil_block_mandal": FieldMeta("Tehsil / Block", FREE_TEXT),
    "owner.address.district": FieldMeta("District", DROPDOWN, "DISTRICTS"),
    "owner.address.police_station": FieldMeta("Police Station", DROPDOWN, "STATIONS"),
    "owner.address.pincode": FieldMeta("Pincode", FREE_TEXT),
    "owner.address.state": FieldMeta("State", FREE_TEXT),
}

# Mandatory subset (shown with ⚠ if empty)
OWNER_MANDATORY = {
    "owner.first_name",
    "owner.last_name",
    "owner.occupation",
    "owner.address.village_town_city",
    "owner.address.district",
    "owner.address.police_station",
}

# ── Tenant personal fields ───────────────────────────────────────────────────
TENANT_PERSONAL_FIELDS: dict[str, FieldMeta] = {
    "tenant.first_name": FieldMeta("First Name", FREE_TEXT),
    "tenant.middle_name": FieldMeta("Middle Name", FREE_TEXT),
    "tenant.last_name": FieldMeta("Last Name", FREE_TEXT),
    "tenant.gender": FieldMeta("Gender", FREE_TEXT),
    "tenant.relative_name": FieldMeta("Relative Name", FREE_TEXT),
    "tenant.relation_type": FieldMeta("Relation Type", DROPDOWN, "RELATION_TYPES"),
    "tenant.dob": FieldMeta("Date of Birth", DATE),
    "tenant.address_verification_doc_type": FieldMeta("ID Proof Type", DROPDOWN, "ADDRESS_DOC_TYPES"),
    "tenant.address_verification_doc_no": FieldMeta("ID Proof No.", FREE_TEXT),
    "tenant.purpose_of_tenancy": FieldMeta("Purpose of Tenancy", DROPDOWN, "TENANCY_PURPOSES"),
    "tenant.occupation": FieldMeta("Occupation", DROPDOWN, "OCCUPATIONS"),
}

TENANT_PERSONAL_MANDATORY = {
    "tenant.first_name",
    "tenant.last_name",
    "tenant.address_verification_doc_type",
    "tenant.address_verification_doc_no",
    "tenant.purpose_of_tenancy",
}

# ── Tenant tenanted premises address (always Delhi) ──────────────────────────
TENANTED_ADDR_FIELDS: dict[str, FieldMeta] = {
    "tenant.tenanted_address.house_no": FieldMeta("House No.", FREE_TEXT),
    "tenant.tenanted_address.street_name": FieldMeta("Street Name", FREE_TEXT),
    "tenant.tenanted_address.colony_locality_area": FieldMeta("Colony / Locality", FREE_TEXT),
    "tenant.tenanted_address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "tenant.tenanted_address.district": FieldMeta("District (Delhi)", DROPDOWN, "DISTRICTS"),
    "tenant.tenanted_address.police_station": FieldMeta("Police Station", DROPDOWN, "STATIONS"),
    "tenant.tenanted_address.pincode": FieldMeta("Pincode", FREE_TEXT),
}

TENANTED_ADDR_MANDATORY = {
    "tenant.tenanted_address.village_town_city",
    "tenant.tenanted_address.district",
    "tenant.tenanted_address.police_station",
}

# ── Tenant permanent address ─────────────────────────────────────────────────
PERM_ADDR_FIELDS: dict[str, FieldMeta] = {
    "tenant.address.house_no": FieldMeta("House No.", FREE_TEXT),
    "tenant.address.street_name": FieldMeta("Street Name", FREE_TEXT),
    "tenant.address.colony_locality_area": FieldMeta("Colony / Locality", FREE_TEXT),
    "tenant.address.village_town_city": FieldMeta("Village / Town / City", FREE_TEXT),
    "tenant.address.district": FieldMeta("District", DROPDOWN, "DISTRICTS"),
    "tenant.address.police_station": FieldMeta("Police Station", DROPDOWN, "STATIONS"),
    "tenant.address.state": FieldMeta("State", FREE_TEXT),
    "tenant.address.country": FieldMeta("Country", FREE_TEXT),
    "tenant.address.pincode": FieldMeta("Pincode", FREE_TEXT),
}

PERM_ADDR_MANDATORY = {
    "tenant.address.village_town_city",
    "tenant.address.country",
}
