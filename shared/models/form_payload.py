from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class AddressData(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    house_no: Optional[str] = None
    street_name: Optional[str] = None
    colony_locality_area: Optional[str] = None
    village_town_city: Optional[str] = None
    tehsil_block_mandal: Optional[str] = None
    district: Optional[str] = None
    police_station: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class OwnerData(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    relative_name: Optional[str] = None
    relation_type: Optional[str] = None
    dob: Optional[str] = None
    mobile_no: Optional[str] = None
    address_verification_doc_no: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[AddressData] = None


class TenantData(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    last_name: Optional[str] = None
    relative_name: Optional[str] = None
    relation_type: Optional[str] = None
    dob: Optional[str] = None
    address_verification_doc_type: Optional[str] = None
    address_verification_doc_no: Optional[str] = None
    purpose_of_tenancy: Optional[str] = None
    address: Optional[AddressData] = None           # tenant permanent address
    previous_address: Optional[AddressData] = None
    tenanted_address: Optional[AddressData] = None  # always Delhi


class FormPayload(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    owner: Optional[OwnerData] = None
    tenant: Optional[TenantData] = None

    def is_submittable(self) -> bool:
        if not self.owner or not self.tenant:
            return False

        # Owner mandatory fields
        if not (self.owner.first_name and self.owner.last_name and self.owner.occupation):
            return False
        owner_addr = self.owner.address
        if not owner_addr:
            return False
        if not (owner_addr.village_town_city and owner_addr.district and owner_addr.police_station):
            return False

        # Tenant personal mandatory fields
        if not (
            self.tenant.first_name
            and self.tenant.last_name
            and self.tenant.purpose_of_tenancy
            and self.tenant.address_verification_doc_type
            and self.tenant.address_verification_doc_no
        ):
            return False

        # Tenant tenanted premises address (always Delhi — all three mandatory)
        ta = self.tenant.tenanted_address
        if not ta:
            return False
        if not (ta.village_town_city and ta.district and ta.police_station):
            return False

        # Tenant permanent address (village_town_city + country mandatory;
        # state/district/police_station are best-effort for non-Delhi states)
        pa = self.tenant.address
        if not pa:
            return False
        if not (pa.village_town_city and pa.country):
            return False

        return True

    def owner_missing_mandatory(self) -> list[str]:
        """Return dot-path list of owner mandatory fields that are still empty."""
        missing = []
        o = self.owner
        if not o or not o.first_name:
            missing.append("owner.first_name")
        if not o or not o.last_name:
            missing.append("owner.last_name")
        if not o or not o.occupation:
            missing.append("owner.occupation")
        addr = o.address if o else None
        if not addr or not addr.village_town_city:
            missing.append("owner.address.village_town_city")
        if not addr or not addr.district:
            missing.append("owner.address.district")
        if not addr or not addr.police_station:
            missing.append("owner.address.police_station")
        return missing

    def tenant_personal_missing_mandatory(self) -> list[str]:
        """Return dot-path list of tenant personal mandatory fields that are still empty."""
        missing = []
        t = self.tenant
        if not t or not t.first_name:
            missing.append("tenant.first_name")
        if not t or not t.last_name:
            missing.append("tenant.last_name")
        if not t or not t.address_verification_doc_type:
            missing.append("tenant.address_verification_doc_type")
        if not t or not t.address_verification_doc_no:
            missing.append("tenant.address_verification_doc_no")
        if not t or not t.purpose_of_tenancy:
            missing.append("tenant.purpose_of_tenancy")
        return missing

    def tenant_perm_addr_missing_mandatory(self) -> list[str]:
        """Return dot-path list of tenant permanent address mandatory fields that are still empty."""
        missing = []
        pa = self.tenant.address if self.tenant else None
        if not pa or not pa.village_town_city:
            missing.append("tenant.address.village_town_city")
        if not pa or not pa.country:
            missing.append("tenant.address.country")
        return missing

    def tenanted_addr_missing_mandatory(self) -> list[str]:
        """Return dot-path list of tenanted premises address mandatory fields that are still empty."""
        missing = []
        ta = self.tenant.tenanted_address if self.tenant else None
        if not ta or not ta.village_town_city:
            missing.append("tenant.tenanted_address.village_town_city")
        if not ta or not ta.district:
            missing.append("tenant.tenanted_address.district")
        if not ta or not ta.police_station:
            missing.append("tenant.tenanted_address.police_station")
        return missing
