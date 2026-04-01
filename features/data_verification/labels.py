from __future__ import annotations

FIELD_LABELS: dict[str, str] = {
    "owner.first_name": "Owner first name",
    "owner.last_name": "Owner last name",
    "owner.relative_name": "Owner relative name",
    "owner.relation_type": "Owner relation type",
    "owner.address.house_no": "Owner house number",
    "owner.address.colony_locality_area": "Owner colony/locality/area",
    "owner.address.village_town_city": "Owner village/town/city",
    "owner.address.district": "Owner district",
    "owner.address.police_station": "Owner police station",
    "owner.address.pincode": "Owner pincode",
    "tenant.first_name": "Tenant first name",
    "tenant.last_name": "Tenant last name",
    "tenant.address_verification_doc_no": "Tenant Aadhaar number",
    "tenant.relative_name": "Tenant relative name",
    "tenant.relation_type": "Tenant relation type",
    "tenant.dob": "Tenant date of birth",
    "tenant.tenanted_address.district": "Tenant district",
    "tenant.tenanted_address.police_station": "Tenant police station",
}


def field_label(field_path: str) -> str:
    explicit = FIELD_LABELS.get(field_path)
    if explicit:
        return explicit
    leaf = field_path.split(".")[-1].replace("_", " ").strip()
    return leaf.title() if leaf else field_path
