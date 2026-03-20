from shared.models.form_payload import AddressData, FormPayload, OwnerData, TenantData
from utils.aadhaar import validate_aadhaar


assert validate_aadhaar("499118665246")[0], "Owner test Aadhaar failed Verhoeff — replace it"
assert validate_aadhaar("300000000001")[0], "Tenant test Aadhaar failed Verhoeff — replace it"


def make_sample_payload() -> FormPayload:
    owner_address = AddressData(
        house_no="47-B",
        street_name="Pusa Road",
        colony_locality_area="Rajinder Nagar",
        village_town_city="New Delhi",
        tehsil_block_mandal=None,
        district="CENTRAL",
        police_station="KAROL BAGH",
        pincode="110060",
        state="DELHI",
        country="INDIA",
    )

    owner = OwnerData(
        first_name="Arjun",
        last_name="Mehta",
        relative_name="Suresh Mehta",
        relation_type="Father",
        dob="1975-03-12",
        occupation="BUSINESS",
        address_verification_doc_no="499118665246",
        address=owner_address,
    )

    tenant_address_permanent = AddressData(
        house_no="B-22",
        street_name="Saket Main Road",
        colony_locality_area="Saket",
        village_town_city="New Delhi",
        tehsil_block_mandal=None,
        district="SOUTH",
        police_station="SAKET",
        pincode="110017",
        state="DELHI",
        country="INDIA",
    )

    tenant_address_tenanted = AddressData(
        house_no="F-14",
        street_name="Press Enclave Road",
        colony_locality_area="Hauz Khas",
        village_town_city="New Delhi",
        tehsil_block_mandal=None,
        district="SOUTH",
        police_station="HAUZ KHAS",
        pincode="110016",
        state="DELHI",
        country="INDIA",
    )

    tenant = TenantData(
        first_name="Priya",
        last_name="Nair",
        relative_name="Ramesh Nair",
        relation_type="Father",
        dob="2001-07-22",
        address_verification_doc_type="Aadhar Card",
        address_verification_doc_no="300000000001",
        purpose_of_tenancy="Residential",
        address=tenant_address_permanent,
        tenanted_address=tenant_address_tenanted,
    )

    return FormPayload(owner=owner, tenant=tenant)
