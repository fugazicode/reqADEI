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
    last_name: Optional[str] = None
    relative_name: Optional[str] = None
    relation_type: Optional[str] = None
    dob: Optional[str] = None
    address_verification_doc_type: Optional[str] = None
    address_verification_doc_no: Optional[str] = None
    purpose_of_tenancy: Optional[str] = None
    address: Optional[AddressData] = None
    previous_address: Optional[AddressData] = None
    tenanted_address: Optional[AddressData] = None


class FormPayload(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    owner: Optional[OwnerData] = None
    tenant: Optional[TenantData] = None

    def is_submittable(self) -> bool:
        if not self.owner or not self.tenant:
            return False
        if not self.owner.first_name or not self.owner.last_name or not self.owner.occupation:
            return False
        if (
            not self.tenant.first_name
            or not self.tenant.last_name
            or not self.tenant.purpose_of_tenancy
            or not self.tenant.address_verification_doc_type
        ):
            return False
        if not self.tenant.tenanted_address:
            return False
        tenanted = self.tenant.tenanted_address
        required_address_fields = [
            tenanted.village_town_city,
            tenanted.country,
            tenanted.state,
            tenanted.district,
            tenanted.police_station,
        ]
        return all(required_address_fields)
