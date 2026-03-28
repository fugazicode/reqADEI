
import asyncio  # add this
import logging
import os
import re
import tempfile
from datetime import date, datetime

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from shared.models.form_payload import FormPayload


DISTRICT_VALUES: dict[str, str] = {
    "CENTRAL": "8162",
    "DWARKA": "8176",
    "EAST": "8168",
    "IGI AIRPORT": "8169",
    "NEW DELHI": "8165",
    "NORTH": "8166",
    "NORTH EAST": "8173",
    "NORTH WEST": "8172",
    "OUTER DISTRICT": "8174",
    "OUTER NORTH": "8991",
    "ROHINI": "8959",
    "SHAHDARA": "8957",
    "SOUTH": "8167",
    "SOUTH WEST": "8171",
    "SOUTH-EAST": "8955",
    "WEST": "8170",
}

POLICE_STATION_VALUES: dict[str, str] = {
    "ANAND PARBAT": "8162001",
    "CHANDNI MAHAL": "8162008",
    "D.B.G. ROAD": "8162038",
    "DARYA GANJ": "8162010",
    "EAST PAHARGANJ": "8162011",
    "HAUZ QAZI": "8162015",
    "I.P.ESTATE": "8162016",
    "JAMA MASJID": "8162019",
    "KAMLA MARKET": "8162023",
    "KAROL BAGH": "8162026",
    "NABI KARIM": "8162030",
    "PAHAR GANJ": "8162041",
    "PATEL NAGAR": "8162042",
    "PRASAD NAGAR": "8162040",
    "RAJINDER NAGAR": "8162045",
    "RANJIT NAGAR": "8162056",
    "BABA HARIDAS NAGAR": "8176009",
    "BINDA PUR": "8176001",
    "CHHAWALA": "8176007",
    "DABRI": "8176002",
    "DWARKA NORTH": "8176004",
    "DWARKA SOUTH": "8176003",
    "JAFFARPUR KALAN": "8176006",
    "MOHAN GARDEN": "8176012",
    "NAJAF GARH": "8176010",
    "SECTOR 23 DWARKA": "8176005",
    "UTTAM NAGAR": "8176008",
    "GHAZIPUR": "8168010",
    "KALYANPURI": "8168013",
    "LAXMI NAGAR": "8168054",
    "MADHU VIHAR": "8168023",
    "MANDAWLI FAZAL PUR": "8168024",
    "MAYUR VIHAR PH-I": "8168026",
    "NEW ASHOK NAGAR": "8168028",
    "PANDAV NAGAR": "8168050",
    "PATPARGANJ INDUSTRIAL AREA": "8168053",
    "PREET VIHAR": "8168030",
    "SHAKARPUR": "8168052",
    "DOMESTIC AIRPORT": "8169001",
    "I.G.I.AIRPORT": "8169002",
    "BARAKHAMBA ROAD": "8165002",
    "CHANKYA PURI": "8165007",
    "CONNAUGHT PLACE": "8165011",
    "IITF,Pragati Maidan": "8165012",
    "KARTAVYA PATH": "8165013",
    "MANDIR MARG": "8165015",
    "NORTH AVENUE": "8165038",
    "PARLIAMENT STREET": "8165022",
    "SOUTH AVENUE": "8165037",
    "TILAK MARG": "8165035",
    "TUGHLAK ROAD": "8165036",
    "BARA HINDU RAO": "8166004",
    "BURARI": "8166052",
    "CIVIL LINES": "8166007",
    "GULABI BAGH": "8166024",
    "KASHMERI GATE": "8166016",
    "KOTWALI": "8166018",
    "LAHORI GATE": "8166023",
    "MAURICE NAGAR": "8166010",
    "ROOP NAGAR": "8166031",
    "SADAR BAZAR": "8166038",
    "SARAI ROHILLA": "8166039",
    "SUBZI MANDI": "8166041",
    "TIMARPUR": "8166051",
    "WAZIRABAD": "8166054",
    "BHAJAN PURA": "8173005",
    "DAYAL PUR": "8173061",
    "GOKUL PURI": "8173054",
    "HARSH VIHAR": "8173055",
    "JAFRABAD": "8173058",
    "JYOTI NAGAR": "8173056",
    "KARAWAL NAGAR": "8173016",
    "KHAJURI KHAS": "8173015",
    "NAND NAGRI": "8173025",
    "NEW USMANPUR": "8173030",
    "SEELAMPUR": "8173042",
    "SHASTRI PARK": "8173060",
    "SONIA VIHAR": "8173057",
    "WELCOME": "8173045",
    "ADARSH NAGAR": "8172003",
    "ASHOK VIHAR": "8172006",
    "BHARAT NAGAR": "8172007",
    "JAHANGIR PURI": "8172014",
    "KESHAV PURAM": "8172025",
    "MAHENDRA PARK": "8172051",
    "MAURYA ENCLAVE": "8172049",
    "MODEL TOWN": "8172017",
    "MUKHERJEE NAGAR": "8172030",
    "SHALIMAR BAGH": "8172035",
    "SUBHASH PLACE": "8172047",
    "MANGOL PURI": "8174005",
    "MUNDKA": "8174025",
    "NANGLOI": "8174021",
    "NIHAL VIHAR": "8174022",
    "PASCHIM VIHAR EAST": "8174026",
    "PASCHIM VIHAR WEST": "8174027",
    "RAJ PARK": "8174029",
    "RANHOLA": "8174020",
    "RANI BAGH": "8174028",
    "SULTANPURI": "8174011",
    "ALIPUR": "8991006",
    "BAWANA": "8991004",
    "BHALSWA DAIRY": "8991003",
    "NARELA": "8991007",
    "NARELA INDUSTRIAL AREA": "8991001",
    "SAMAIPUR BADLI": "8991008",
    "SHAHBAD DAIRY": "8991005",
    "SWAROOP NAGAR": "8991002",
    "AMAN VIHAR": "8959016",
    "BEGUM PUR": "8959003",
    "BUDH VIHAR": "8959014",
    "K.N. KATJU MARG": "8959007",
    "KANJHAWALA": "8959015",
    "NORTH ROHINI": "8959011",
    "PRASHANT VIHAR": "8959008",
    "PREM NAGAR": "8959013",
    "SOUTH ROHINI": "8959010",
    "VIJAY VIHAR": "8959009",
    "ANAND VIHAR": "8957002",
    "FARSH BAZAR": "8957006",
    "G.T.B. ENCLAVE": "8957009",
    "GANDHI NAGAR": "8957004",
    "GEETA COLONY": "8957005",
    "JAGAT PURI": "8957011",
    "KRISHNA NAGAR": "8957003",
    "MANSAROVAR PARK": "8957008",
    "SEEMAPURI": "8957010",
    "SHAHDARA": "8957007",
    "VIVEK VIHAR": "8957001",
    "AMBEDKAR NAGAR": "8167064",
    "CHITRANJAN PARK": "8167062",
    "DEFENCE COLONY": "8167010",
    "FATEHPUR BERI": "8167012",
    "GREATER KAILASH": "8167061",
    "HAUZ KHAS": "8167017",
    "K.M. PUR": "8167023",
    "LODI COLONY": "8167028",
    "MAIDAN GARHI": "8167066",
    "MALVIYA NAGAR": "8167033",
    "MEHRAULI": "8167032",
    "NEB SARAI": "8167057",
    "SAKET": "8167056",
    "SANGAM VIHAR": "8167063",
    "TIGRI": "8167067",
    "DELHI CANTT": "8171011",
    "KAPASHERA": "8171030",
    "KISHAN GARH": "8171066",
    "PALAM VILLAGE": "8171057",
    "R. K. PURAM": "8171060",
    "SAFDARJUNG ENCLAVE": "8171067",
    "SAGAR PUR": "8171054",
    "SAROJINI NAGAR": "8171068",
    "SOUTH CAMPUS": "8171061",
    "VASANT KUNJ NORTH": "8171062",
    "VASANT KUNJ SOUTH": "8171063",
    "VASANT VIHAR": "8171064",
    "AMAR COLONY": "8955007",
    "BADARPUR": "8955012",
    "GOVIND PURI": "8955002",
    "HAZARAT NIZAMUDDIN": "8955005",
    "JAIT PUR": "8955001",
    "JAMIA NAGAR": "8955004",
    "KALANDI KUNJ": "8955019",
    "KALKAJI": "8955009",
    "LAJPAT NAGAR": "8955006",
    "NEW FRIENDS COLONY": "8955003",
    "OKHLA INDUSTRIAL AREA": "8955013",
    "PUL PRAHLAD PUR": "8955017",
    "SARITA VIHAR": "8955011",
    "SHAHEEN BAGH": "8955020",
    "SUNLIGHT COLONY": "8955016",
    "HARI NAGAR": "8170015",
    "INDER PURI": "8170064",
    "JANAK PURI": "8170021",
    "KHYALA": "8170062",
    "KIRTI NAGAR": "8170025",
    "MAYAPURI": "8170028",
    "MOTI NAGAR": "8170029",
    "NARAINA": "8170063",
    "PUNJABI BAGH": "8170043",
    "RAJOURI GARDEN": "8170037",
    "TILAK NAGAR": "8170051",
    "VIKASPURI": "8170060",
}

STATE_VALUES: dict[str, str] = {
    "ANDAMAN & NICOBAR": "1",
    "ANDHRA PRADESH": "2",
    "ARUNACHAL PRADESH": "3",
    "ASSAM": "4",
    "BIHAR": "5",
    "CHANDIGARH": "6",
    "DAMAN & DIU": "7",
    "DELHI": "8",
    "DADRA & NAGAR HAVELI": "9",
    "GOA": "10",
    "GUJARAT": "11",
    "HIMACHAL PRADESH": "12",
    "HARYANA": "13",
    "JAMMU & KASHMIR": "14",
    "KERALA": "15",
    "KARNATAKA": "16",
    "LAKSHADWEEP": "17",
    "MEGHALAYA": "18",
    "MAHARASHTRA": "19",
    "MANIPUR": "20",
    "MADHYA PRADESH": "21",
    "MIZORAM": "22",
    "NAGALAND": "23",
    "ODISHA": "24",
    "PUNJAB": "25",
    "PUDUCHERRY": "26",
    "RAJASTHAN": "27",
    "SIKKIM": "28",
    "TAMIL NADU": "29",
    "TRIPURA": "30",
    "UTTAR PRADESH": "31",
    "WEST BENGAL": "32",
    "CHHATTISGARH": "33",
    "JHARKHAND": "34",
    "UTTARAKHAND": "35",
    "TELANGANA": "40",
    "LADAKH": "41",
}


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
            timeout=30000,
        )

    async def _navigate_to_address_subtab(self) -> None:
        """
        Clicks the Address sub-tab within Tenant Information.
        Waits for the Tenanted Premises Address button to be visible
        as confirmation that the Address sub-tab content has loaded.
        """
        await self._page.click('[href="javascript:TabView.switchTab(1,1);"]')
        await self._page.wait_for_selector(
            "text=Tenanted Premises Address",
            state="visible",
            timeout=30000,
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

    async def _setup_ajax_csrf(self) -> None:
        token = await self._page.evaluate(
            """() => {
                const raw = document.cookie.split('; ')
                    .find(r => r.startsWith('XSRF-TOKEN='));
                if (!raw) return '';
                return decodeURIComponent(raw.split('=')[1] || '');
            }"""
        )
        print(f"[CSRF] Initial token: '{token}'")
        if not token:
            self._logger.warning(
                "[CSRF] WARNING — token empty at setup time, will retry per-request"
            )

        def _response_handler(response) -> None:
            try:
                if any(
                    key in response.url
                    for key in ["getstates", "getdistricts", "getpolicestations"]
                ):
                    print(f"[CSRF] RESPONSE {response.status} {response.url}")
            except Exception as exc:
                self._logger.warning(
                    "[CSRF] WARNING — response handler error: %s",
                    exc,
                )

        self._page.on("response", _response_handler)

        async def inject_csrf(route, request) -> None:
            try:
                if self._page.is_closed():
                    try:
                        await route.continue_()
                    except Exception as exc:
                        self._logger.warning(
                            "[CSRF] ERROR — route.continue_() failed: %s",
                            exc,
                        )
                    return

                live_token = await self._page.evaluate(
                    """() => {
                        const raw = document.cookie.split('; ')
                            .find(r => r.startsWith('XSRF-TOKEN='));
                        if (!raw) return '';
                        return decodeURIComponent(raw.split('=')[1] || '');
                    }"""
                )
                print(f"[CSRF] Injecting token '{live_token}' for {request.url}")
                if "getpolicestations" in request.url:
                    print("[CSRF] Station request firing")

                if not live_token:
                    print(
                        f"[CSRF] WARNING — token empty at intercept time for {request.url}, "
                        "continuing without header"
                    )
                    await route.continue_()
                    return

                headers = dict(request.headers)
                headers["X-XSRF-TOKEN"] = live_token
                await route.continue_(headers=headers)
            except Exception as exc:
                self._logger.warning(
                    "[CSRF] ERROR — route handler failed for %s: %s",
                    request.url,
                    exc,
                )
                try:
                    await route.continue_()
                except Exception as nested_exc:
                    self._logger.warning(
                        "[CSRF] ERROR — route.continue_() also failed: %s",
                        nested_exc,
                    )

        await self._page.route("**/getstates.htm", inject_csrf)
        await self._page.route("**/getdistricts.htm", inject_csrf)
        await self._page.route("**/getpolicestations.htm", inject_csrf)
        print(
            "[CSRF] Interceptors registered for getstates, getdistricts, getpolicestations"
        )

    async def _js_select(self, field_name: str, value: str) -> None:
        """Set a <select> value by option-value and fire its change event.

        Raises ValueError if the option is not currently in the dropdown.
        """
        await self._page.evaluate(
            """([name, val]) => {
                const el = document.querySelector('[name="' + name + '"]');
                if (!el) throw new Error('Element not found: ' + name);
                el.value = val;
                if (el.value !== val) {
                    const available = Array.from(el.options).map(o => o.value).join(', ');
                    throw new Error(
                        'Option "' + val + '" not present in <select name="' + name + '">. ' +
                        'Available values: [' + available + ']'
                    );
                }
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            [field_name, value],
        )

    async def _wait_for_options(self, field_name: str, timeout: int = 20000) -> bool:
        try:
            await self._page.wait_for_function(
                f"document.querySelector('[name=\"{field_name}\"]') && "
                f"document.querySelector('[name=\"{field_name}\"]').options.length > 1",
                timeout=timeout,
            )
            return True
        except Exception:
            self._logger.warning("Options for '%s' did not populate in time", field_name)
            return False

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

        district_value = DISTRICT_VALUES.get(district)
        if not district_value:
            self._logger.warning("Unknown district '%s' — skipping", district)
            return

        station_value = None
        if station:
            station_value = POLICE_STATION_VALUES.get(station.upper())

        try:
            async with self._page.expect_response(
                lambda r: "getpolicestations" in r.url,
                timeout=30000,
            ) as response_info:
                await self._js_select(district_field, district_value)

            await response_info.value
        except PlaywrightTimeoutError:
            self._logger.warning(
                "District selection did not trigger station load for '%s'",
                district,
            )
            if station_value is None:
                self._logger.warning(
                    "No station value available for '%s' — hidden station will be blank",
                    station,
                )
            await self._page.evaluate(
                """([hiddenDistrict, hiddenStation, districtVal, stationVal]) => {
                    const d = document.querySelector('[name="' + hiddenDistrict + '"]');
                    const s = document.querySelector('[name="' + hiddenStation + '"]');
                    if (d) d.value = districtVal || '';
                    if (s) s.value = stationVal || '';
                }""",
                [
                    hidden_district_field,
                    hidden_station_field,
                    district_value,
                    station_value,
                ],
            )
            return

        if not await self._wait_for_options(station_field):
            if district:
                await self._select_by_label(district_field, district)
                await self._wait_for_options(station_field)

        if station:
            if station_value:
                await self._js_select(station_field, station_value)
            else:
                self._logger.warning(
                    "Unknown station '%s' — attempting label fallback",
                    station,
                )
                await self._select_by_label(station_field, station)

        hidden_d = await self._page.input_value(f'[name="{hidden_district_field}"]')
        hidden_s = await self._page.input_value(f'[name="{hidden_station_field}"]')
        if not hidden_d:
            self._logger.warning(
                "Hidden district field '%s' empty — forcing value '%s'",
                hidden_district_field,
                district_value,
            )
            await self._page.evaluate(
                """([name, val]) => {
                    const el = document.querySelector('[name="' + name + '"]');
                    if (el) el.value = val;
                }""",
                [hidden_district_field, district_value],
            )
        if not hidden_s and station_value:
            self._logger.warning(
                "Hidden station field '%s' empty — forcing value '%s'",
                hidden_station_field,
                station_value,
            )
            await self._page.evaluate(
                """([name, val]) => {
                    const el = document.querySelector('[name="' + name + '"]');
                    if (el) el.value = val;
                }""",
                [hidden_station_field, station_value],
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
        if self._payload.tenant.address.state:
            state_value = STATE_VALUES.get(self._payload.tenant.address.state.upper())
            if state_value:
                try:
                    async with self._page.expect_response(
                        lambda r: "getdistricts" in r.url,
                        timeout=15000,
                    ) as response_info:
                        await self._js_select("tenantPermanentState", state_value)
                    await response_info.value
                    await self._wait_for_options("tenantPermanentDistrict")
                except PlaywrightTimeoutError:
                    self._logger.warning(
                        "State selection did not trigger district load for '%s'",
                        self._payload.tenant.address.state,
                    )
                    if not await self._wait_for_options("tenantPermanentDistrict"):
                        await self._select_by_label(
                            "tenantPermanentState",
                            self._payload.tenant.address.state,
                        )
                        await self._wait_for_options("tenantPermanentDistrict")
            else:
                self._logger.warning(
                    "Unknown permanent address state '%s' — skipping",
                    self._payload.tenant.address.state,
                )

        if self._payload.tenant.address.district:
            district_value = DISTRICT_VALUES.get(self._payload.tenant.address.district.upper())
            if not district_value:
                self._logger.warning(
                    "Unknown permanent address district '%s' — skipping",
                    self._payload.tenant.address.district,
                )
                return

            try:
                async with self._page.expect_response(
                    lambda r: "getpolicestations" in r.url,
                    timeout=15000,
                ) as response_info:
                    await self._js_select("tenantPermanentDistrict", district_value)

                await response_info.value
            except PlaywrightTimeoutError:
                self._logger.warning(
                    "District selection did not trigger station load for '%s'",
                    self._payload.tenant.address.district,
                )

            if not await self._wait_for_options("tenantPermanentPoliceStation"):
                self._logger.warning(
                    "Police stations did not populate for '%s'",
                    self._payload.tenant.address.district,
                )

            if self._payload.tenant.address.police_station:
                station_value = POLICE_STATION_VALUES.get(self._payload.tenant.address.police_station.upper())
                if station_value:
                    await self._js_select("tenantPermanentPoliceStation", station_value)
                else:
                    self._logger.warning(
                        "Unknown permanent address police station '%s' — fallback to label select",
                        self._payload.tenant.address.police_station,
                    )
                    await self._select_by_label(
                        "tenantPermanentPoliceStation",
                        self._payload.tenant.address.police_station,
                    )

    async def _fill_owner_tab(self) -> None:
        if not getattr(self, "_csrf_setup_done", False):
            await self._setup_ajax_csrf()
            self._csrf_setup_done = True

        await self._page.click("text=Owner Information")
        await self._page.wait_for_selector(
            '[name="ownerFirstName"]',
            state="visible",
            timeout=30000,
        )

        await self._fill_text("ownerFirstName", self._payload.owner.first_name)
        await self._fill_text("ownerMiddleName", self._payload.owner.middle_name)
        await self._fill_text("ownerLastName", self._payload.owner.last_name)
        await self._fill_text("ownerRelativeName", self._payload.owner.relative_name)
        await self._select_by_label("ownerOccupation", self._payload.owner.occupation)
        await self._select_by_label("ownerRelationType", self._payload.owner.relation_type)
        await self._fill_text("ownerMobile1", self._payload.owner.mobile_no)

        if not self._payload.owner.address:
            return

        await self._fill_text("ownerHouseNo", self._payload.owner.address.house_no)
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
        await self._fill_text("ownerPincode", self._payload.owner.address.pincode)

        # Country/state are pre-selected in static HTML (India/Delhi).
        # Changing either triggers checkForOtherCountry and clears downstream selects.
        # Leave them untouched to preserve district/station options.

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
            timeout=30000,
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
        await self._page.wait_for_selector("#rbno", state="visible", timeout=120000)
        await self._page.click("#rbno")


    async def _fill_document_upload(self, image_bytes: bytes) -> None:
        # Step 1: Click Tenant Information tab and activate Personal Information sub-tab
        await self._page.click("text=Tenant Information")
        await self._click_inner_tab("Personal Information", "tenantFirstName")
        if not image_bytes:
            self._logger.warning("No image bytes provided — skipping document upload")
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            tmp.write(image_bytes)
            tmp.close()
            await self._page.set_input_files("#fileField2", tmp.name)
            # Wait for file input to have a value
            await self._page.wait_for_function(
                "document.querySelector('#fileField2') && document.querySelector('#fileField2').value !== ''",
                timeout=60000,
            )
            # Select fileTypeCd2 = "2" (ScanPhoto) using direct id selector
            await self._page.select_option("#fileTypeCd2", value="2")
            await self._page.fill("#filedescriptionId2", "Aadhaar Card")
        finally:
            os.unlink(tmp.name)

    _DUMMY_PDF_BYTES = (
        b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << >> >>\nendobj\n'
        b'4 0 obj\n<< /Length 9 >>\nstream\nBT\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000015 00000 n \n0000000062 00000 n \n0000000111 00000 n \n0000000220 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n273\n%%EOF\n'
    )

    async def _save_download(self, download) -> bytes:
        """Save a Playwright Download object to a temp file and return its bytes."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await download.save_as(tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _retrieve_pdf(self, request_number: str) -> bytes:
        try:
            # Step 1: Hover over "Tenant Registration" in the top menu
            await self._page.hover("text=Tenant Registration")
            await self._page.wait_for_selector(
                'a[href="searchviewtenentverifydetails.htm"]',
                state="visible",
                timeout=120000,
            )

            # Step 2: Click "View Tenant Registration Detail" in the dropdown
            await self._page.click('a[href="searchviewtenentverifydetails.htm"]')
            await self._page.wait_for_selector(
                "text=Search and View the Status of Application",
                state="visible",
                timeout=300000,
            )

            # Step 3: Click the "Search" button (no input)
            await self._page.click("input[value='Search'], button:has-text('Search')")
            await self._page.wait_for_selector(
                "text=Most Recent Tenant Registration",
                state="visible",
                timeout=300000,
            )

            # Step 4: Find the row with the correct request_number and click it
            await self._page.click(f"text={request_number}")
            await self._page.wait_for_selector(
                "text=View Tenant Registration Detail",
                state="visible",
                timeout=300000,
            )

            # Step 5: Click Print — opens a new tab via window.open().
            # Register the new tab listener BEFORE clicking to avoid missing the event.
            context = self._page.context
            async with context.expect_page() as new_page_info:
                await self._page.click("#print")
            new_tab = await new_page_info.value
            await new_tab.wait_for_load_state("domcontentloaded", timeout=60000)

            # Fetch the PDF directly using the authenticated session context.
            tab_url = new_tab.url
            self._logger.warning(
                "_retrieve_pdf: new tab opened — fetching URL: %s", tab_url
            )
            response = await context.request.get(tab_url, timeout=60000)
            pdf_bytes = await response.body()
            if pdf_bytes[:4] == b"%PDF":
                self._logger.warning(
                    "_retrieve_pdf: successfully retrieved %d bytes for request_number=%s",
                    len(pdf_bytes),
                    request_number,
                )
                return pdf_bytes

            self._logger.warning(
                "_retrieve_pdf: new tab did not contain a PDF — "
                "URL: %r, content length: %d, first 100 bytes: %s",
                tab_url,
                len(pdf_bytes),
                pdf_bytes[:100],
            )
            raise RuntimeError(
                f"New tab did not contain a PDF for request_number={request_number} "
                f"— URL was {tab_url!r}"
            )

        except Exception as exc:
            self._logger.warning(
                "_retrieve_pdf failed for request_number=%s: %r — "
                "falling back to _DUMMY_PDF_BYTES (442 bytes). "
                "Check navigation and tab handling above.",
                request_number,
                exc,
            )
            return self._DUMMY_PDF_BYTES

    async def _fill_affidavit_tab(self) -> None:
        await self._page.click("text=Affidavit")
        await self._page.wait_for_selector("#allTrue", state="visible", timeout=120000)
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
        self._page.on("dialog", lambda dialog: asyncio.ensure_future(dialog.dismiss()))

        captured_body: list[str] = []

        async def handle_submit_response(route, request) -> None:
            if request.method != "POST":
                await route.continue_()
                return
            try:
                response = await route.fetch(timeout=0)
                body = await response.text()
                captured_body.append(body)
                # Fulfill with a blank page to stop the browser
                # from following the redirect to ERR_FILE_NOT_FOUND
                await route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<html><body>OK</body></html>",
                )
            except Exception as exc:
                self._logger.warning(
                    "Route handler failed to fetch response: %s", exc
                )
                await route.continue_()

        await self._page.route(
            "**/addtenantpgverification.htm",
            handle_submit_response,
        )


        await self._page.click("#submit123", no_wait_after=True)

        # Poll until the route handler populates captured_body.
        # The handler fires asynchronously when the server responds to the POST.
        # Give it up to 60 seconds in 500ms increments.
        deadline = 60
        interval = 0.5
        elapsed = 0.0
        while not captured_body and elapsed < deadline:
            await asyncio.sleep(interval)
            elapsed += interval

        if not captured_body:
            self._logger.warning(
                "Route handler did not capture POST response within %ds", deadline
            )

        # Unregister the route so it does not interfere with further navigation.
        await self._page.unroute("**/addtenantpgverification.htm")

        if captured_body:
            content = captured_body[0]
        else:
            self._logger.warning(
                "Route handler did not capture response — falling back to page body"
            )
            content = await self._page.inner_text("body")


        self._logger.warning("Response content (first 1000 chars): %s", content[:1000])

        if "Unable to process your request" in content:
            raise RuntimeError("Portal server rejected the submission.")

        match = re.search(
            r"Service\s+Request\s+Number\s+(\d+)",
            content,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

        # Fallback — broader pattern in case portal wording changes
        match = re.search(r"Request\s+Number[:\s]+(\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"(\d{6,})", content)
        if match:
            self._logger.warning(
                "Primary regex did not match — returning first long number: %s",
                match.group(1),
            )
            return match.group(1)

        self._logger.warning("Request number not found in captured response")
        return "UNKNOWN"
