from __future__ import annotations

from shared.models.form_payload import AddressData



def to_address_data(data: dict) -> AddressData:
    return AddressData(**{k: v for k, v in data.items() if k in AddressData.model_fields})
