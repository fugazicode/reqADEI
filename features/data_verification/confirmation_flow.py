from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from features.data_verification.keyboards import confirm_edit_keyboard
from features.data_verification.labels import field_label
from features.data_verification.states import DataVerificationStates
from shared.models.session import FormSession
from utils.aadhaar import mask_aadhaar
from utils.payload_accessor import PayloadAccessor

# Field paths that must be filled via the picker UI, never via free-text input.
# When these fields are missing, show_next_field() returns "missing_picker"
# so callers can route to the district/station picker instead of AWAITING_EDIT_INPUT.
_DISTRICT_FIELDS = {
    "owner.address.district",
    "tenant.tenanted_address.district",
}
_STATION_FIELDS = {
    "owner.address.police_station",
    "tenant.tenanted_address.police_station",
}


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
        """Show the next field in the confirmation queue.

        Returns:
            "confirm"        — field has a value; confirm/edit keyboard shown.
            "missing"        — field is empty and accepts free-text input;
                               caller should set AWAITING_EDIT_INPUT.
            "missing_picker" — field is empty but must be filled via the
                               district/station picker UI (never free-text);
                               caller should route to the appropriate picker.
            None             — queue is empty; nothing to show.
        """
        if not self.session.confirmation_queue:
            return None

        field_path = self.session.confirmation_queue[0]
        label = field_label(field_path)
        value = PayloadAccessor.get(self.session.payload, field_path)

        if value is None or value == "":
            self.session.current_editing_field = field_path

            # District and station fields must always go through the picker UI.
            # Returning "missing_picker" tells the caller to open the picker
            # instead of dropping into free-text AWAITING_EDIT_INPUT.
            if field_path in _DISTRICT_FIELDS or field_path in _STATION_FIELDS:
                if self.session.last_prompt_message_id:
                    try:
                        await message.bot.delete_message(
                            chat_id=message.chat.id,
                            message_id=self.session.last_prompt_message_id,
                        )
                    except Exception:
                        pass
                    self.session.last_prompt_message_id = None
                return "missing_picker"

            # All other missing fields accept free-text input.
            if self.session.last_prompt_message_id:
                try:
                    await message.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=self.session.last_prompt_message_id,
                    )
                except Exception:
                    pass
            sent = await message.answer(f"{label} is missing. Please provide the value.")
            self.session.last_prompt_message_id = sent.message_id
            return "missing"

        display_value = value
        if field_path.endswith("address_verification_doc_no"):
            display_value = mask_aadhaar(str(value))

        if self.session.last_prompt_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=self.session.last_prompt_message_id,
                )
            except Exception:
                pass
        sent = await message.answer(
            f"Please confirm:\n{label}: {display_value}",
            reply_markup=confirm_edit_keyboard(field_path),
        )
        self.session.last_prompt_message_id = sent.message_id
        return "confirm"
