from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import date, datetime

from playwright.async_api import Page

from shared.models.form_payload import FormPayload


class FormFiller:
    def __init__(self, page: Page, payload: FormPayload) -> None:
        self._page = page
        self._payload = payload
        self._logger = logging.getLogger(__name__)

    async def fill(self, image_bytes: bytes) -> str:
        await self._fill_owner_tab()
        await self._fill_tenant_personal_tab()
        await self._navigate_to_address_subtab()
        await self._fill_tenant_address_tenanted()
        await self._fill_tenant_address_permanent()
        await self._fill_family_member_tab()
        await self._fill_document_upload(image_bytes)
        await self._fill_affidavit_tab()
        return await self._submit_and_get_result()

    async def _click_inner_tab(self, button_text: str, visible_field_name: str) -> None:
        """
        Clicks an inner navigation button within a sub-tab and waits
        for a specific field to become visible, confirming the section loaded.

        button_text: The exact visible text on the button to click.
        visible_field_name: The name attribute of a field inside that section,
                            used as the signal that the section is now active.
        """
        await self._page.click(f"text={button_text}")
        await self._page.wait_for_selector(
            f'[name="{visible_field_name}"]',
            state="visible",
            timeout=10000,
        )

    async def _navigate_to_address_subtab(self) -> None:
        """
        Clicks the Address sub-tab within Tenant Information.
        Waits for the Tenanted Premises Address button to be visible
        as confirmation that the Address sub-tab content has loaded.
        """
        await self._page.click("text=Address")
        await self._page.wait_for_selector(
            "text=Tenanted Premises Address",
            state="visible",
            timeout=10000,
        )

    async def _fill_text(self, field_name: str, value: str | None) -> None:
        if value is None or value == "":
            return
        await self._page.fill(f'[name="{field_name}"]', value)

    async def _select_by_label(self, field_name: str, label: str | None) -> None:
        if label is None or label == "":
            return
        try:
            await self._page.select_option(f'[name="{field_name}"]', label=label)
        except Exception:
            self._logger.warning(
                "Could not select label '%s' for field '%s'",
                label,
                field_name,
            )

    async def _select_district_and_station(
        self,
        district: str | None,
        station: str | None,
        district_field: str,
        station_field: str,
        hidden_district_field: str,
        hidden_station_field: str,
    ) -> None:
        if not district:
            return

        async with self._page.expect_response(
            lambda r: "getpolicestations" in r.url,
            timeout=15000,
        ) as response_info:
            await self._page.select_option(
                f'[name="{district_field}"]',
                label=district,
            )

        await response_info.value

        await self._page.wait_for_function(
            f"document.querySelector('[name=\"{station_field}\"]').options.length > 1",
            timeout=10000,
        )

        if station:
            await self._page.select_option(
                f'[name="{station_field}"]',
                label=station,
            )

        hidden_d = await self._page.input_value(f'[name="{hidden_district_field}"]')
        hidden_s = await self._page.input_value(f'[name="{hidden_station_field}"]')
        if not hidden_d or not hidden_s:
            self._logger.warning(
                "Hidden fields not populated after district/station selection — "
                "district_field=%s hidden_district=%s hidden_station=%s",
                district_field,
                hidden_d,
                hidden_s,
            )

    async def _fill_tenant_address_tenanted(self) -> None:
        await self._click_inner_tab(
            "Tenanted Premises Address",
            "tenantPresentHouseNo",
        )
        if not self._payload.tenant.tenanted_address:
            self._logger.warning("Tenant tenanted address missing in payload")
            return

        await self._fill_text(
            "tenantPresentHouseNo",
            self._payload.tenant.tenanted_address.house_no,
        )
        await self._fill_text(
            "tenantPresentStreetName",
            self._payload.tenant.tenanted_address.street_name,
        )
        await self._fill_text(
            "tenantPresentColony",
            self._payload.tenant.tenanted_address.colony_locality_area,
        )
        await self._fill_text(
            "tenantPresentVillage",
            self._payload.tenant.tenanted_address.village_town_city,
        )
        await self._fill_text(
            "tenantPresentTehsil",
            self._payload.tenant.tenanted_address.tehsil_block_mandal,
        )
        await self._fill_text(
            "tenantPresentPincode",
            self._payload.tenant.tenanted_address.pincode,
        )
        await self._select_by_label("tenantPresentCountry", "INDIA")
        await self._select_by_label("tenantPresentState", "DELHI")

        await self._select_district_and_station(
            self._payload.tenant.tenanted_address.district,
            self._payload.tenant.tenanted_address.police_station,
            "tenantPresentDistrict",
            "tenantPresentPoliceStation",
            "hidtenantPrestDistrict",
            "hidtenantPresPStation",
        )

    async def _fill_tenant_address_permanent(self) -> None:
        await self._click_inner_tab(
            "Permanent Address",
            "tenantPermanentHouseNo",
        )
        if not self._payload.tenant.address:
            self._logger.warning("Tenant permanent address missing in payload")
            return

        await self._fill_text(
            "tenantPermanentHouseNo",
            self._payload.tenant.address.house_no,
        )
        await self._fill_text(
            "tenantPermanentStreetName",
            self._payload.tenant.address.street_name,
        )
        await self._fill_text(
            "tenantPermanentColony",
            self._payload.tenant.address.colony_locality_area,
        )
        await self._fill_text(
            "tenantPermanentVillage",
            self._payload.tenant.address.village_town_city,
        )
        await self._fill_text(
            "tenantPermanentTehsil",
            self._payload.tenant.address.tehsil_block_mandal,
        )
        await self._fill_text(
            "tenantPermanentPincode",
            self._payload.tenant.address.pincode,
        )
        await self._select_by_label("tenantPermanentCountry", "INDIA")

        if self._payload.tenant.address.state:
            try:
                await self._page.select_option(
                    '[name="tenantPermanentState"]',
                    label=self._payload.tenant.address.state,
                )
            except Exception:
                self._logger.warning(
                    "Could not select permanent address state: %s",
                    self._payload.tenant.address.state,
                )

        if self._payload.tenant.address.district:
            await self._select_district_and_station(
                self._payload.tenant.address.district,
                self._payload.tenant.address.police_station,
                "tenantPermanentDistrict",
                "tenantPermanentPoliceStation",
                "hidtenantPermtDistrict",
                "hidtenantPermPStation",
            )

    async def _fill_owner_tab(self) -> None:
        await self._page.click("text=Owner Information")
        await self._page.wait_for_selector(
            '[name="ownerFirstName"]',
            state="visible",
            timeout=15000,
        )

        await self._fill_text("ownerFirstName", self._payload.owner.first_name)
        await self._fill_text("ownerMiddleName", self._payload.owner.middle_name)
        await self._fill_text("ownerLastName", self._payload.owner.last_name)
        await self._fill_text("ownerRelativeName", self._payload.owner.relative_name)
        await self._select_by_label("ownerOccupation", self._payload.owner.occupation)
        await self._select_by_label(
            "ownerRelationType",
            self._payload.owner.relation_type,
        )
        await self._fill_text("ownerMobile1", self._payload.owner.mobile_no)

        if self._payload.owner.address:
            await self._fill_text(
                "ownerHouseNo",
                self._payload.owner.address.house_no,
            )
            await self._fill_text(
                "ownerStreetName",
                self._payload.owner.address.street_name,
            )
            await self._fill_text(
                "ownerColony",
                self._payload.owner.address.colony_locality_area,
            )
            await self._fill_text(
                "ownerVillage",
                self._payload.owner.address.village_town_city,
            )
            await self._fill_text(
                "ownerTehsil",
                self._payload.owner.address.tehsil_block_mandal,
            )
            await self._fill_text(
                "ownerPincode",
                self._payload.owner.address.pincode,
            )
            await self._select_by_label("ownerCountry", "INDIA")
            await self._select_by_label("ownerState", "DELHI")
            await self._select_district_and_station(
                self._payload.owner.address.district,
                self._payload.owner.address.police_station,
                "ownerDistrict",
                "ownerPoliceStation",
                "hiddenownerDistrict",
                "hiddenownerPStation",
            )

    async def _fill_tenant_personal_tab(self) -> None:
        await self._page.click("text=Tenant Information")
        await self._page.wait_for_selector(
            '[name="tenantFirstName"]',
            state="visible",
            timeout=15000,
        )

        await self._fill_text("tenantFirstName", self._payload.tenant.first_name)
        await self._fill_text("tenantMiddleName", self._payload.tenant.middle_name)
        await self._fill_text("tenantLastName", self._payload.tenant.last_name)
        await self._fill_text(
            "tenantRelativeName",
            self._payload.tenant.relative_name,
        )
        await self._select_by_label("tenantGender", self._payload.tenant.gender)
        await self._select_by_label(
            "tenantOccupation",
            self._payload.tenant.occupation,
        )
        await self._select_by_label(
            "tenantRelationType",
            self._payload.tenant.relation_type,
        )
        await self._select_by_label(
            "tenantAddressDocuments",
            self._payload.tenant.address_verification_doc_type,
        )
        await self._fill_text(
            "tenantAddressDocumentsNo",
            self._payload.tenant.address_verification_doc_no,
        )
        await self._select_by_label(
            "tenancypurpose",
            self._payload.tenant.purpose_of_tenancy,
        )

        if self._payload.tenant.dob:
            dob_obj = datetime.strptime(self._payload.tenant.dob, "%Y-%m-%d")
            formatted_dob = dob_obj.strftime("%d/%m/%Y")
            await self._page.fill(
                "#tenantVerificationTenantcommonPaneldateOfBirth",
                formatted_dob,
            )
            await self._page.wait_for_timeout(1000)
            age_year = await self._page.input_value(
                '[id="tenantVerificationTenant.commonPanelAgeYear"]'
            )
            if not age_year:
                today = date.today()
                age = today.year - dob_obj.year - (
                    (today.month, today.day) < (dob_obj.month, dob_obj.day)
                )
                await self._page.fill(
                    '[id="tenantVerificationTenant.commonPanelAgeYear"]',
                    str(age),
                )

    async def _fill_family_member_tab(self) -> None:
        await self._page.click("text=Family Member Information")
        await self._page.wait_for_selector("#rbno", state="visible", timeout=10000)
        await self._page.click("#rbno")

    async def _fill_document_upload(self, image_bytes: bytes) -> None:
        if not image_bytes:
            self._logger.warning("No image bytes provided — skipping document upload")
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            tmp.write(image_bytes)
            tmp.close()
            await self._page.set_input_files("#fileField2", tmp.name)
            await self._page.wait_for_selector(
                "#fileField2 ~ table tbody tr",
                timeout=15000,
            )
        finally:
            os.unlink(tmp.name)

    async def _fill_affidavit_tab(self) -> None:
        await self._page.click("text=Affidavit")
        await self._page.wait_for_selector("#allTrue", state="visible", timeout=10000)
        await self._page.click("#hasAnyCriminalRecord1")
        await self._page.check("#allTrue")
        is_checked = await self._page.is_checked("#allTrue")
        if not is_checked:
            await self._page.click("#allTrue")
            is_checked = await self._page.is_checked("#allTrue")
            if not is_checked:
                raise RuntimeError(
                    "Declaration of truth checkbox could not be checked. "
                    "Submission cannot proceed."
                )

    async def _submit_and_get_result(self) -> str:
        await self._page.click("#submit123")

        await self._page.wait_for_selector(
            "text=Please Wait, Processing Data",
            timeout=15000,
        )
        await self._page.wait_for_selector(
            "text=Please Wait, Processing Data",
            state="hidden",
            timeout=60000,
        )

        content = await self._page.inner_text("body")

        if "Unable to process your request" in content:
            raise RuntimeError("Portal server rejected the submission.")

        match = re.search(r"Request\s+Number[:\s]+(\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)

        self._logger.warning("Request number not found on result page")
        return "UNKNOWN"
