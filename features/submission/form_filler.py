from __future__ import annotations

import logging

from playwright.async_api import Page


class FormFiller:
    def __init__(self, page: Page, logger: logging.Logger | None = None) -> None:
        self._page = page
        self._logger = logger or logging.getLogger(__name__)

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
        raise NotImplementedError

    async def _fill_tenant_address_permanent(self) -> None:
        await self._click_inner_tab(
            "Permanent Address",
            "tenantPermanentHouseNo",
        )
        raise NotImplementedError

    async def _fill_owner_tab(self) -> None:
        raise NotImplementedError

    async def _fill_tenant_personal_tab(self) -> None:
        raise NotImplementedError

    async def _fill_family_member_tab(self) -> None:
        raise NotImplementedError

    async def _fill_document_upload(self, image_bytes: bytes) -> None:
        raise NotImplementedError

    async def _fill_affidavit_tab(self) -> None:
        raise NotImplementedError

    async def _submit_and_get_result(self) -> str:
        raise NotImplementedError
