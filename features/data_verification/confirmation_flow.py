from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from features.data_verification.keyboards import confirm_edit_keyboard
from features.data_verification.states import DataVerificationStates
from shared.models.session import FormSession
from utils.payload_accessor import PayloadAccessor


class ConfirmationFlow:
    def __init__(self, session: FormSession) -> None:
        self.session = session

    @staticmethod
    def build_queue(session: FormSession) -> None:
        person = session.current_confirming_person
        if person == "owner":
            session.confirmation_queue = [
                "owner.first_name",
                "owner.last_name",
                "owner.relative_name",
                "owner.relation_type",
                "owner.address.house_no",
                "owner.address.colony_locality_area",
                "owner.address.village_town_city",
                "owner.address.district",
                "owner.address.police_station",
                "owner.address.pincode",
            ]
            return

        session.confirmation_queue = [
            "tenant.first_name",
            "tenant.last_name",
            "tenant.address_verification_doc_no",
            "tenant.relative_name",
            "tenant.relation_type",
            "tenant.dob",
        ]

    async def show_next_field(self, message: Message, state: FSMContext) -> str | None:
        if not self.session.confirmation_queue:
            return None

        field_path = self.session.confirmation_queue[0]
        value = PayloadAccessor.get(self.session.payload, field_path)
        if value is None or value == "":
            self.session.current_editing_field = field_path
            await message.answer(f"{field_path} is missing. Please type the value.")
            return "missing"

        await message.answer(
            f"Please confirm:\n{field_path}: {value}",
            reply_markup=confirm_edit_keyboard(field_path),
        )
        return "confirm"
