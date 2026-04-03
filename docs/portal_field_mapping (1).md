# Delhi Police CCTNS — Tenant Registration Portal
## Complete Field Mapping Reference
### Source: Live log capture + form_filler.py cross-reference
### Notation: `field_name` = DOM name attribute | ★ = portal-locked (hardcoded, not user-selectable) | * = mandatory
### Revision: Address scope rules, Documents sub-tab corrections, Family tab clarification, Previous address mandatory logic added

---

## LEGEND

| Symbol | Meaning |
|--------|---------|
| `*` | Mandatory — portal enforces or code raises SubmissionValidationError |
| `**COND**` | Conditionally mandatory — portal enforces when parent condition is met (see section notes) |
| `★` | Portal-locked — value is hardcoded by portal HTML, cannot be changed by user or code |
| `[AJAX]` | Options populated via XHR after a parent selection changes |
| `[STATIC]` | Options pre-loaded in page HTML on page load, no AJAX needed |
| `[HIDDEN]` | Hidden input field, value written directly to DOM (not user-visible) |
| `[AUTO]` | Code fills this automatically, not driven by user data |
| `[N/A]` | "Not Applicable" sentinel — portal-accepted value when field is not applicable (e.g. foreign country has no Indian state) |

---

## GLOBAL ADDRESS SCOPE RULES

These rules apply uniformly across every address section in the form. They govern which fields become applicable or not applicable depending on the country selected. Read before filling any address section.

### Rule 1 — Tenanted Premises Address is always Delhi, always India

The Tenanted Premises Address (where the tenant will reside) is portal-locked to `INDIA` and `DELHI`. The portal renders these as single-option dropdowns — no other selection is possible. District must be one of the 16 Delhi districts. Police Station is loaded via AJAX after district selection. This rule has no exceptions.

### Rule 2 — All other address sections allow any country or state

The Owner Permanent Address and both Tenant address sections (Previous and Permanent) accept addresses from any Indian state or any foreign country. The portal provides a 216-country dropdown for Country in all of these sections.

### Rule 3 — Foreign country selection makes State, District, Police Station "Not Applicable"

When a non-India country is selected in any address section (other than Tenanted Premises), the portal accepts the following sentinel values for the dependent fields and does not raise a validation error:

| Field | Not Applicable Sentinel Value | Not Applicable Label |
|---|---|---|
| State | `99` | `---Not applicable---` |
| District | `99999` | `---Not applicable---` |
| Police Station | `99999999` | `---Not applicable---` |

These sentinel values are **accepted by the portal** as valid submissions. They must be written to the DOM directly for out-of-country addresses.

### Rule 4 — Village/Town/City is always required regardless of country

Even for foreign addresses (e.g. country = UAE), the `Village/Town/City` field must be filled. Write the city name of the person's address (e.g. `"DUBAI"`, `"LONDON"`). The portal enforces this field across all address sections and will block submission if it is empty.

### Rule 5 — Owner address country/state must not be changed once district is loaded

For the Owner Address specifically: the portal pre-selects `INDIA` and `DELHI` and loads the district dropdown immediately. Programmatically changing Country or State at this point triggers the `checkForOtherCountry()` JS handler which clears all downstream district and police station options. Therefore the code intentionally leaves Country and State untouched on the Owner tab and only writes District and Police Station directly by value. If the owner's actual address is outside Delhi, the district/station fields will silently fail — this is a documented pre-existing risk.

---

## TAB 1 — Owner Information

**Navigation:** Click tab text `"Owner Information"`
**Readiness signal:** `[name="ownerFirstName"]` becomes visible

---

### 1.1 Personal Details

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| UID | *(not in code)* | Input | No | Not filled by automation |
| First Name | `ownerFirstName` | Input | **Yes** | Code: `fill_text` |
| Middle Name | `ownerMiddleName` | Input | No | Code: `fill_text` |
| Last Name | `ownerLastName` | Input | No | Code: `fill_text` |
| Occupation | `ownerOccupation` | Dropdown | **Yes*** | Code: `_select_by_label(required=True)` |
| Relation Type | `ownerRelationType` | Dropdown | No | Code: `_select_by_label` |
| Relative Name | `ownerRelativeName` | Input | No | Code: `fill_text` |
| Email ID | *(not in code)* | Input | No | Not filled by automation |
| Mobile No. | `ownerMobile1` | Input | No | Prefix `+91` shown in portal UI |
| Landline No. | *(not in code)* | Input | No | Prefix `+91` shown in portal UI |
| Office Address/Phone No. | *(not in code)* | Textarea | No | Not filled by automation |

---

### 1.2 Dropdown: `ownerOccupation` — Occupation *

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 1 | ACADEMICIAN |
| 2 | ACCOUNTANT |
| 3 | AGENT |
| 4 | AIR LINES STAFF |
| 5 | AIRPORT STAFF |
| 6 | ARCHITECT |
| 7 | ARTISAN |
| 8 | ARTIST |
| 138 | ASST. SUPERVISOR |
| 9 | BANK EMPLOYEE |
| 121 | BARBER |
| 120 | BLACK SMITH |
| 12 | BROKER |
| 13 | BUILDER |
| 122 | BULLOCK CART DRIVER |
| 114 | BUS CONDUCTOR |
| 14 | BUSINESS |
| 15 | CABLE OPERATORS |
| 16 | CARPENTER |
| 137 | CHAIRMAN |
| 17 | CLEANER BUS |
| 18 | CLEANER TRUCK |
| 19 | COBBLER |
| 20 | COMPANY EXECUTIVE |
| 21 | COMPUTER PROFESSIONAL |
| 22 | CONTRACTOR |
| 132 | COOK |
| 23 | COURIER |
| 24 | CRAFTSMAN |
| 25 | CREW |
| 211 | Daily Wage Earner |
| 26 | DEALER - ANTIQUE |
| 27 | DEALER - SKIN & FUR |
| 28 | DEFENCE PERSONNEL |
| 139 | DOMESTIC HELPER |
| 29 | DOMESTIC SERVANT |
| 126 | DRAUGHTSMAN |
| 116 | DRIVER |
| 30 | DRIVER - BUS |
| 31 | DRIVER - CAR |
| 32 | DRIVER - CART |
| 33 | DRIVER - TAXI |
| 34 | DRIVER - TRUCK |
| 110 | DRIVER-AUTORICKSHAW |
| 36 | ELECTED REPRESENTATIVES |
| 37 | ELECTRICIAN |
| 106 | EMPLOYED IN PRIVATE FIRMS |
| 38 | ENGINEERS |
| 39 | EXPORTER |
| 40 | FACTORY WORKER |
| 41 | FARMER/CULTIVATOR |
| 42 | FINANCIER |
| 133 | FIREMAN |
| 111 | FISHERMAN |
| 44 | GARDNER |
| 45 | GOLD SMITH |
| 46 | GOVT. OFFICIAL GAZETTED |
| 47 | GOVT. OFFICIAL NON-GAZETTED |
| 48 | HAWKERS |
| 134 | HELPER |
| 50 | HOME-GUARD |
| 51 | HOTEL EMPLOYEE |
| 52 | HOUSE HELP - HIRED |
| 53 | HOUSEWIFE |
| 54 | IMPORTER |
| 55 | INDUSTRIALIST |
| 56 | JAIL STAFF |
| 57 | JUDICIAL OFFICER |
| 58 | JUGGLERS |
| 59 | LABOURER |
| 60 | LAUNDERER (DHOBI) |
| 61 | LAW PRACTITIONER |
| 127 | LINEMAN |
| 62 | LITERARY PERSON |
| 136 | MANAGER |
| 63 | MASON |
| 64 | MECHANIC |
| 65 | MEDIA PERSON |
| 66 | MEDICAL PRACTITIONER |
| 67 | MERCENARY |
| 68 | MILKMAN |
| 69 | MINES EMPLOYEE |
| 70 | MONEY LENDER |
| 129 | NGOS EMPLOYEE |
| 143 | NOT KNOWN |
| 142 | NOT WORKING |
| 140 | OTHERS |
| 72 | PARA MEDICAL STAFF |
| 112 | PEON |
| 205 | PERSONNEL - ASSAM RIFLE |
| 203 | PERSONNEL - BSF |
| 204 | PERSONNEL - CISF |
| 202 | PERSONNEL - CRPF |
| 201 | PERSONNEL - ITBP |
| 206 | PERSONNEL - NSG |
| 200 | PERSONNEL - SSB |
| 104 | PHOTOGRAPHER |
| 73 | PILOT |
| 74 | PLUMBER |
| 75 | POLICE OFFICER |
| 76 | POLITICIANS |
| 77 | PORTER |
| 78 | POSTAL STAFF |
| 207 | Professional/Salaried Persons - Central/UT Govt Servants |
| 209 | Professional/Salaried Persons - Other Statutory Body/ etc. |
| 210 | Professional/Salaried Persons - Public Sector Undertaking |
| 208 | Professional/Salaried Persons - State Govt Servants |
| 115 | PROFESSOR |
| 80 | RAILWAYS STAFF |
| 81 | REAL ESTATE DEALER |
| 107 | RELATIVE/FRIEND |
| 82 | RELIGIOUS PERSON |
| 119 | RETIRED EMPLOYEE |
| 118 | RETIRED GOVT. EMPLOYEE |
| 125 | RICKSHAW PULLER |
| 83 | SALESMAN |
| 84 | SANITARY WORKER |
| 85 | SECURITY GUARD |
| 141 | SERVICE |
| 86 | SHOP EMPLOYEE |
| 87 | SHOPKEEPER |
| 117 | SOCIAL SERVICE |
| 89 | SPORTS PERSON |
| 90 | STUDENT |
| 135 | SUPERVISOR |
| 91 | SURVEYOR |
| 92 | SWEEPER |
| 105 | TAILOR |
| 130 | TALLY CLERK |
| 93 | TEACHER |
| 94 | TECHNICIAN |
| 95 | TELECOM STAFF |
| 109 | TOURIST |
| 123 | TRACTOR DRIVER |
| 96 | TRADER |
| 113 | TRAVELLING AS CO-PASSENGER |
| 97 | UNEMPLOYED |
| 98 | UTILITY SERIVCEMAN |
| 100 | VENDOR |
| 101 | VIDEO EXHIBITORS |
| 102 | WATCHMEN |
| 103 | WEAVER |
| 131 | WELDER |
| 128 | WORKING IN CPO/PARA MILITARY ORGANIZATION |

> **Note:** `ownerOccupation` and `tenantOccupation` share the exact same option list and values.

---

### 1.3 Dropdown: `ownerRelationType` — Relation Type *

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 5 | Father |
| 7 | Guardian |
| 8 | Husband |
| 6 | Mother |
| 9 | Wife |

> **Note:** `ownerRelationType` and `tenantRelationType` share the exact same option list and values.

---

### 1.4 Owner Permanent Address

> **Scope:** Can be any Indian state or any foreign country. See Global Address Scope Rules above.

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| House No. | `ownerHouseNo` | Input | No | |
| Street Name | `ownerStreetName` | Input | No | |
| Colony/Locality/Area | `ownerColony` | Input | No | |
| Village/Town/City | `ownerVillage` | Input | **Yes*** | Always required — fill city name even for foreign addresses (e.g. `"DUBAI"`). See Rule 4. |
| Tehsil/Block/Mandal | `ownerTehsil` | Input | No | |
| Pincode | `ownerPincode` | Input | No | |
| Country | *(not touched by code)* | Dropdown `★` | No | Portal pre-selects `INDIA` (value `80`). Code leaves untouched — changing it clears district/station. If owner is from another country, this field is not currently updated by automation. See Rule 5. |
| State | *(not touched by code)* | Dropdown `★` | No | Portal pre-selects `DELHI` (value `8`). Code leaves untouched for same reason. |
| District | `ownerDistrict` | Dropdown [AJAX] | **Yes** (portal-enforced) | Triggers `getpolicestations.htm` on change. Only Delhi districts available when state=DELHI. |
| Police Station | `ownerPoliceStation` | Dropdown [AJAX] | **Yes** (portal-enforced) | Populated after district selected |
| *(hidden)* | `hiddenownerDistrict` | [HIDDEN] | — | Written by `_select_district_and_station()` as fallback |
| *(hidden)* | `hiddenownerPStation` | [HIDDEN] | — | Written by `_select_district_and_station()` as fallback |

---

### 1.5 Dropdown: `ownerDistrict` / `tenantPresentDistrict` — District (Delhi)

All 16 Delhi districts pre-loaded statically in page DOM (confirmed from log). No AJAX call needed to populate these.

| Value | Label |
|---|---|
| 8162 | CENTRAL |
| 8176 | DWARKA |
| 8168 | EAST |
| 8169 | IGI AIRPORT |
| 8165 | NEW DELHI |
| 8166 | NORTH |
| 8173 | NORTH EAST |
| 8172 | NORTH WEST |
| 8174 | OUTER DISTRICT |
| 8991 | OUTER NORTH |
| 8959 | ROHINI |
| 8957 | SHAHDARA |
| 8167 | SOUTH |
| 8171 | SOUTH WEST |
| 8955 | SOUTH-EAST |
| 8170 | WEST |

---

### 1.6 Police Stations Per District

Stations are AJAX-loaded via `getpolicestations.htm` (parameter name: **TBD — not yet captured**) after district selection triggers the `change` event.

#### CENTRAL (8162)
| Value | Station Label |
|---|---|
| 8162001 | ANAND PARBAT |
| 8162008 | CHANDNI MAHAL |
| 8162038 | D.B.G. ROAD |
| 8162010 | DARYA GANJ |
| 8162011 | EAST PAHARGANJ |
| 8162015 | HAUZ QAZI |
| 8162016 | I.P.ESTATE |
| 8162019 | JAMA MASJID |
| 8162023 | KAMLA MARKET |
| 8162026 | KAROL BAGH |
| 8162030 | NABI KARIM |
| 8162041 | PAHAR GANJ |
| 8162042 | PATEL NAGAR |
| 8162040 | PRASAD NAGAR |
| 8162045 | RAJINDER NAGAR |
| 8162056 | RANJIT NAGAR |

#### DWARKA (8176)
| Value | Station Label |
|---|---|
| 8176009 | BABA HARIDAS NAGAR |
| 8176001 | BINDA PUR |
| 8176007 | CHHAWALA |
| 8176002 | DABRI |
| 8176004 | DWARKA NORTH |
| 8176003 | DWARKA SOUTH |
| 8176006 | JAFFARPUR KALAN |
| 8176012 | MOHAN GARDEN |
| 8176010 | NAJAF GARH |
| 8176005 | SECTOR 23 DWARKA |
| 8176008 | UTTAM NAGAR |

#### EAST (8168)
| Value | Station Label |
|---|---|
| 8168010 | GHAZIPUR |
| 8168013 | KALYANPURI |
| 8168054 | LAXMI NAGAR |
| 8168023 | MADHU VIHAR |
| 8168024 | MANDAWLI FAZAL PUR |
| 8168026 | MAYUR VIHAR PH-I |
| 8168028 | NEW ASHOK NAGAR |
| 8168050 | PANDAV NAGAR |
| 8168053 | PATPARGANJ INDUSTRIAL AREA |
| 8168030 | PREET VIHAR |
| 8168052 | SHAKARPUR |

> **Note:** The EAST district station list was live-captured from the portal page (`_page_tenantPresentPoliceStation` — the scraper happened to have EAST selected at capture time). All other district station lists are sourced from `POLICE_STATION_VALUES` in `form_filler.py` and are unconfirmed against the live portal.

#### IGI AIRPORT (8169)
| Value | Station Label |
|---|---|
| 8169001 | DOMESTIC AIRPORT |
| 8169002 | I.G.I.AIRPORT |

#### NEW DELHI (8165)
| Value | Station Label |
|---|---|
| 8165002 | BARAKHAMBA ROAD |
| 8165007 | CHANKYA PURI |
| 8165011 | CONNAUGHT PLACE |
| 8165012 | IITF,Pragati Maidan |
| 8165013 | KARTAVYA PATH |
| 8165015 | MANDIR MARG |
| 8165038 | NORTH AVENUE |
| 8165022 | PARLIAMENT STREET |
| 8165037 | SOUTH AVENUE |
| 8165035 | TILAK MARG |
| 8165036 | TUGHLAK ROAD |

#### NORTH (8166)
| Value | Station Label |
|---|---|
| 8166004 | BARA HINDU RAO |
| 8166052 | BURARI |
| 8166007 | CIVIL LINES |
| 8166024 | GULABI BAGH |
| 8166016 | KASHMERI GATE |
| 8166018 | KOTWALI |
| 8166023 | LAHORI GATE |
| 8166010 | MAURICE NAGAR |
| 8166031 | ROOP NAGAR |
| 8166038 | SADAR BAZAR |
| 8166039 | SARAI ROHILLA |
| 8166041 | SUBZI MANDI |
| 8166051 | TIMARPUR |
| 8166054 | WAZIRABAD |

#### NORTH EAST (8173)
| Value | Station Label |
|---|---|
| 8173005 | BHAJAN PURA |
| 8173061 | DAYAL PUR |
| 8173054 | GOKUL PURI |
| 8173055 | HARSH VIHAR |
| 8173058 | JAFRABAD |
| 8173056 | JYOTI NAGAR |
| 8173016 | KARAWAL NAGAR |
| 8173015 | KHAJURI KHAS |
| 8173025 | NAND NAGRI |
| 8173030 | NEW USMANPUR |
| 8173042 | SEELAMPUR |
| 8173060 | SHASTRI PARK |
| 8173057 | SONIA VIHAR |
| 8173045 | WELCOME |

#### NORTH WEST (8172)
| Value | Station Label |
|---|---|
| 8172003 | ADARSH NAGAR |
| 8172006 | ASHOK VIHAR |
| 8172007 | BHARAT NAGAR |
| 8172014 | JAHANGIR PURI |
| 8172025 | KESHAV PURAM |
| 8172051 | MAHENDRA PARK |
| 8172049 | MAURYA ENCLAVE |
| 8172017 | MODEL TOWN |
| 8172030 | MUKHERJEE NAGAR |
| 8172035 | SHALIMAR BAGH |
| 8172047 | SUBHASH PLACE |

#### OUTER DISTRICT (8174)
| Value | Station Label |
|---|---|
| 8174005 | MANGOL PURI |
| 8174025 | MUNDKA |
| 8174021 | NANGLOI |
| 8174022 | NIHAL VIHAR |
| 8174026 | PASCHIM VIHAR EAST |
| 8174027 | PASCHIM VIHAR WEST |
| 8174029 | RAJ PARK |
| 8174020 | RANHOLA |
| 8174028 | RANI BAGH |
| 8174011 | SULTANPURI |

#### OUTER NORTH (8991)
| Value | Station Label |
|---|---|
| 8991006 | ALIPUR |
| 8991004 | BAWANA |
| 8991003 | BHALSWA DAIRY |
| 8991007 | NARELA |
| 8991001 | NARELA INDUSTRIAL AREA |
| 8991008 | SAMAIPUR BADLI |
| 8991005 | SHAHBAD DAIRY |
| 8991002 | SWAROOP NAGAR |

#### ROHINI (8959)
| Value | Station Label |
|---|---|
| 8959016 | AMAN VIHAR |
| 8959003 | BEGUM PUR |
| 8959014 | BUDH VIHAR |
| 8959007 | K.N. KATJU MARG |
| 8959015 | KANJHAWALA |
| 8959011 | NORTH ROHINI |
| 8959008 | PRASHANT VIHAR |
| 8959013 | PREM NAGAR |
| 8959010 | SOUTH ROHINI |
| 8959009 | VIJAY VIHAR |

#### SHAHDARA (8957)
| Value | Station Label |
|---|---|
| 8957002 | ANAND VIHAR |
| 8957006 | FARSH BAZAR |
| 8957009 | G.T.B. ENCLAVE |
| 8957004 | GANDHI NAGAR |
| 8957005 | GEETA COLONY |
| 8957011 | JAGAT PURI |
| 8957003 | KRISHNA NAGAR |
| 8957008 | MANSAROVAR PARK |
| 8957010 | SEEMAPURI |
| 8957007 | SHAHDARA |
| 8957001 | VIVEK VIHAR |

#### SOUTH (8167)
| Value | Station Label |
|---|---|
| 8167064 | AMBEDKAR NAGAR |
| 8167062 | CHITRANJAN PARK |
| 8167010 | DEFENCE COLONY |
| 8167012 | FATEHPUR BERI |
| 8167061 | GREATER KAILASH |
| 8167017 | HAUZ KHAS |
| 8167023 | K.M. PUR |
| 8167028 | LODI COLONY |
| 8167066 | MAIDAN GARHI |
| 8167033 | MALVIYA NAGAR |
| 8167032 | MEHRAULI |
| 8167057 | NEB SARAI |
| 8167056 | SAKET |
| 8167063 | SANGAM VIHAR |
| 8167067 | TIGRI |

#### SOUTH WEST (8171)
| Value | Station Label |
|---|---|
| 8171011 | DELHI CANTT |
| 8171030 | KAPASHERA |
| 8171066 | KISHAN GARH |
| 8171057 | PALAM VILLAGE |
| 8171060 | R. K. PURAM |
| 8171067 | SAFDARJUNG ENCLAVE |
| 8171054 | SAGAR PUR |
| 8171068 | SAROJINI NAGAR |
| 8171061 | SOUTH CAMPUS |
| 8171062 | VASANT KUNJ NORTH |
| 8171063 | VASANT KUNJ SOUTH |
| 8171064 | VASANT VIHAR |

#### SOUTH-EAST (8955)
| Value | Station Label |
|---|---|
| 8955007 | AMAR COLONY |
| 8955012 | BADARPUR |
| 8955002 | GOVIND PURI |
| 8955005 | HAZARAT NIZAMUDDIN |
| 8955001 | JAIT PUR |
| 8955004 | JAMIA NAGAR |
| 8955019 | KALANDI KUNJ |
| 8955009 | KALKAJI |
| 8955006 | LAJPAT NAGAR |
| 8955003 | NEW FRIENDS COLONY |
| 8955013 | OKHLA INDUSTRIAL AREA |
| 8955017 | PUL PRAHLAD PUR |
| 8955011 | SARITA VIHAR |
| 8955020 | SHAHEEN BAGH |
| 8955016 | SUNLIGHT COLONY |

#### WEST (8170)
| Value | Station Label |
|---|---|
| 8170015 | HARI NAGAR |
| 8170064 | INDER PURI |
| 8170021 | JANAK PURI |
| 8170062 | KHYALA |
| 8170025 | KIRTI NAGAR |
| 8170028 | MAYAPURI |
| 8170029 | MOTI NAGAR |
| 8170063 | NARAINA |
| 8170043 | PUNJABI BAGH |
| 8170037 | RAJOURI GARDEN |
| 8170051 | TILAK NAGAR |
| 8170060 | VIKASPURI |

---

## TAB 2 — Tenant Information

---

### SUB-TAB 2A — Personal Information

**Navigation:** Click tab `"Tenant Information"` → click sub-tab `"Personal Information"`
**Readiness signal:** `[name="tenantFirstName"]` becomes visible

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| First Name | `tenantFirstName` | Input | **Yes** | |
| Middle Name | `tenantMiddleName` | Input | No | |
| Last Name | `tenantLastName` | Input | No | |
| Relative Name | `tenantRelativeName` | Input | No | |
| Gender | `tenantGender` | Dropdown | No | |
| Occupation | `tenantOccupation` | Dropdown | No | Same values as `ownerOccupation` |
| Relation Type | `tenantRelationType` | Dropdown | No | Same values as `ownerRelationType` |
| Address Verification Document Type | `tenantAddressDocuments` | Dropdown | **Yes*** | Code: `_select_by_label(required=True)` |
| Address Verification Document No. | `tenantAddressDocumentsNo` | Input | **Yes** | |
| Date of Birth | `#tenantVerificationTenantcommonPaneldateOfBirth` | Date Input | No | Format: `dd/MM/yyyy` |
| Age (Year) | `tenantVerificationTenant.commonPanelAgeYear` | Input | No | Auto-calculated from DOB; written as fallback if portal doesn't compute |
| Purpose of Tenancy | `tenancypurpose` | Dropdown | **Yes*** | Code: `_select_by_label(required=True)` |

---

### 2A.1 Dropdown: `tenantGender` — Gender

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 2 | Female |
| 3 | Male |
| 4 | NOT KNOWN |
| 1 | Transgender |

---

### 2A.2 Dropdown: `tenantAddressDocuments` — Address Verification Document Type *

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 8 | Aadhar Card |
| 7 | Any Other |
| 4 | Arms License |
| 2 | Driving License |
| 10 | Electricity Bill |
| 6 | Income Tax (PAN) Card |
| 1 | Passport |
| 3 | Ration Card |
| 9 | Telephone Bill |
| 5 | Voter Card |

> **Critical:** This is the dropdown that was previously unconfirmed. Labels above are directly from the live log capture (`tenantAddressDocuments` static field). These exact strings must be used as the label argument to `_select_by_label()`.

---

### 2A.3 Dropdown: `tenancypurpose` — Purpose of Tenancy *

Null state: `------------Select------------` (value `0`)

| Value | Label |
|---|---|
| C | commercial |
| R | Residential |

> **Case-sensitive warning:** The portal stores `"commercial"` (lowercase c) and `"Residential"` (title case). The `TENANCY_PURPOSES.normalize()` function in `portal_enums.py` handles normalisation before selection.

---

### SUB-TAB 2B — Documents

**Navigation:** Click `"Tenant Information"` → click sub-tab `"Documents"` → click inner sub-tab `"Personal Information"` (code navigates here first, then uploads)

> The portal shows two upload rows in this sub-tab. Row 1 is for the tenant's photo (optional). Row 2 is for the identity document scan (required). The table below maps each child field of both rows with their exact browser-visible label and the confirmed option values from the live log.

---

#### Upload Row 1 — Photo Of The Tenant *(optional)*

| Portal Label | Element Selector | Type | Required | Notes |
|---|---|---|---|---|
| Photo Of The Tenant | `#fileField1` | File Upload | No | Not filled by automation |
| ↳ File Type | `#fileTypeCd1` | Dropdown | No | Not filled by automation |
| ↳ Description | `#filedescriptionId1` | Input | No | Not filled by automation |

---

#### Upload Row 2 — Scan Copy Of The Identity Documents *

| Portal Label | Element Selector | Type | Required | Filled Value | Notes |
|---|---|---|---|---|---|
| Scan Copy Of The Identity Documents | `#fileField2` | File Upload | **Yes*** | Aadhaar image bytes | Code: `set_input_files("#fileField2", tmp.name)` |
| ↳ File Type | `#fileTypeCd2` | Dropdown [AUTO] | **Yes*** | `ScanPhoto` (value `2`) | Only one valid option exists in the portal. Hardcoded by code via `select_option("#fileTypeCd2", value="2")`. |
| ↳ Description | `#filedescriptionId2` | Input [AUTO] | **Yes*** | `Aadhaar Card` | Description is required specifically for the scan document row. Hardcoded by code via `fill("#filedescriptionId2", "Aadhaar Card")`. |

#### Dropdown: `#fileTypeCd2` — File Type (exact browser options from live log)

| Value | Label (exact, case-sensitive) |
|---|---|
| 0 | `-----------Select------------` *(null state)* |
| 2 | `ScanPhoto` |

> **Single-option confirmed:** Only `ScanPhoto` (value `2`) exists as a valid selection. The hardcoded `value="2"` in `_fill_document_upload` is correct and is the only possible option. No label-based selection is needed — value `"2"` is written directly.

---



### SUB-TAB 2C — Address

**Navigation:** Click `"Tenant Information"` → evaluate JS click on `href="javascript:TabView.switchTab(1,1);"` → wait for text `"Tenanted Premises Address"` to be visible

> **Three address sub-sub-tabs exist.** The filling requirement is:
> - **Tenanted Premises Address** — always required, always Delhi/India (portal-locked).
> - **Previous Address** — not marked mandatory in UI but portal enforces that **at least one** of Previous or Permanent must be filled. The mandatory unmarked fields within it are: `Country`, `State`, `Village/Town/City`, `District`, `Police Station`.
> - **Permanent Address** — same conditional requirement as Previous. At least one of the two must satisfy the portal's hidden mandatory check.
>
> Both Previous and Permanent can be from **any Indian state or any foreign country**. See Global Address Scope Rules.

---

#### SUB-SUB-TAB 2C-i — Tenanted Premises Address

**Navigation:** Click button text `"Tenanted Premises Address"`
**Readiness signal:** `[name="tenantPresentHouseNo"]` becomes visible

> **Scope: ALWAYS Delhi, ALWAYS India. No exceptions.** This is the address of the rented property being registered with Delhi Police. The portal physically locks Country to `INDIA` and State to `DELHI` — both are single-entry dropdowns. The tenant may be from any state or country, but the tenanted property must be in Delhi.

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| House No. | `tenantPresentHouseNo` | Input | No | |
| Street Name | `tenantPresentStreetName` | Input | No | |
| Colony/Locality/Area | `tenantPresentColony` | Input | No | |
| Village/Town/City | `tenantPresentVillage` | Input | **Yes*** | Always required — see Rule 4 |
| Tehsil/Block/Mandal | `tenantPresentTehsil` | Input | No | |
| Pincode | `tenantPresentPincode` | Input | No | |
| Country | `★ PORTAL LOCKED` | Dropdown `★` | **Yes** | Only option: `INDIA` (value `80`). Confirmed single-entry list in live log. |
| State | `★ PORTAL LOCKED` | Dropdown `★` | **Yes** | Only option: `DELHI` (value `8`). Confirmed single-entry list in live log. |
| District | `tenantPresentDistrict` | Dropdown [STATIC] | **Yes*** | All 16 Delhi districts loaded statically — no AJAX needed to populate list. |
| Police Station | `tenantPresentPoliceStation` | Dropdown [AJAX] | **Yes*** | Loaded via `getpolicestations.htm` after district `change` event fires |
| *(hidden)* | `hidtenantPrestDistrict` | [HIDDEN] | — | Written by `_select_district_and_station()` fallback |
| *(hidden)* | `hidtenantPresPStation` | [HIDDEN] | — | Written by `_select_district_and_station()` fallback |

---

#### SUB-SUB-TAB 2C-ii — Previous Address (Tenant's Previous Residence)

**Navigation:** Click button text `"Previous Address"`

> **Scope:** Can be any Indian state or any foreign country. See Global Address Scope Rules.
>
> **Mandatory logic:** Not marked mandatory in the portal UI. However, the portal enforces that **at least one of Previous Address or Permanent Address must be filled** before submission. If this section is the one being filled, the fields marked `**COND**` become mandatory.
>
> **Out-of-country behaviour:** If Country is set to a non-India value → State sentinel `99`, District sentinel `99999`, Police Station sentinel `99999999`. Portal accepts these sentinels. Village/Town/City must still be filled regardless — write the city name (see Rule 4).
>
> **Implementation status:** The current `form_filler.py` does **not** fill this sub-tab. `_fill_tenant_address_permanent()` fills Permanent only. If Previous is ever implemented, it follows the same AJAX chain pattern as Permanent.

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| House No. | `tenantPreviousHouseNo` | Input | No | |
| Street Name | `tenantPreviousStreetName` | Input | No | |
| Colony/Locality/Area | `tenantPreviousColony` | Input | No | |
| Village/Town/City | `tenantPreviousVillage` | Input | **COND*** | Required when section is used. Write city name even for foreign addresses. |
| Tehsil/Block/Mandal | `tenantPreviousTehsil` | Input | No | |
| Pincode | `tenantPreviousPincode` | Input | No | |
| Country | `tenantPreviousCountry` | Dropdown | **COND*** | Required when section is used. Full 216-country list. Default: `INDIA` (value `80`). |
| State | `tenantPreviousState` | Dropdown [AJAX] | **COND*** | Required when section is used. Default sentinel: `---Not applicable---` (value `99`). India → AJAX loads 37 states. Non-India country → leave at sentinel `99`. |
| District | `tenantPreviousDistrict` | Dropdown [AJAX] | **COND*** | Required when section is used. Default sentinel: `---Not applicable---` (value `99999`). Loaded after state selected (India/Delhi). Non-India country → set to sentinel `99999`. |
| Police Station | `tenantPreviousPoliceStation` | Dropdown [AJAX] | **COND*** | Required when section is used. Default sentinel: `---Not applicable---` (value `99999999`). Loaded after district selected. Non-India country → set to sentinel `99999999`. |

#### Not-Applicable Sentinels — Previous Address (foreign country)

| Field | DOM name | Sentinel Value | Sentinel Label |
|---|---|---|---|
| State | `tenantPreviousState` | `99` | `---Not applicable---` |
| District | `tenantPreviousDistrict` | `99999` | `---Not applicable---` |
| Police Station | `tenantPreviousPoliceStation` | `99999999` | `---Not applicable---` |



#### SUB-SUB-TAB 2C-iii — Permanent Address (Tenant's Permanent Residence)

**Navigation:** Click button text `"Permanent Address"`
**Readiness signal:** `[name="tenantPermanentHouseNo"]` becomes visible

> **Scope:** Can be any Indian state or any foreign country. See Global Address Scope Rules.
>
> **Mandatory logic:** Not marked mandatory in the portal UI. However, the portal enforces that **at least one of Previous Address or Permanent Address must be filled** before submission. This is the section currently filled by `_fill_tenant_address_permanent()`. The fields marked `**COND**` are the unmarked-but-enforced mandatory fields when this section is used.
>
> **Out-of-country behaviour:** If Country is set to a non-India value → State sentinel `99`, District sentinel `99999`, Police Station sentinel `99999999`. Portal accepts these sentinels. Village/Town/City must still be filled regardless — write the city name (see Rule 4).

| Portal Label | Field Name | Type | Required | Notes |
|---|---|---|---|---|
| House No. | `tenantPermanentHouseNo` | Input | No | |
| Street Name | `tenantPermanentStreetName` | Input | No | |
| Colony/Locality/Area | `tenantPermanentColony` | Input | No | |
| Village/Town/City | `tenantPermanentVillage` | Input | **COND*** | Portal-enforced when section is used. Write city name even for foreign addresses. |
| Tehsil/Block/Mandal | `tenantPermanentTehsil` | Input | No | |
| Pincode | `tenantPermanentPincode` | Input | No | |
| Country | `tenantPermanentCountry` | Dropdown | **COND*** | Portal-enforced when section is used. Full 216-country list. Default: `INDIA` (value `80`). |
| State | `tenantPermanentState` | Dropdown [AJAX] | **COND*** | Portal-enforced when section is used. Default sentinel: `---Not applicable---` (value `99`). India → AJAX loads 37 states via `STATE_VALUES`. Non-India country → leave at sentinel `99`. |
| District | `tenantPermanentDistrict` | Dropdown [AJAX] | **COND*** | Portal-enforced when section is used. Default: `--------------Select------------` (value `0`). Loaded after state selected. Non-India country → force sentinel `99999` via JS. |
| Police Station | `tenantPermanentPoliceStation` | Dropdown [AJAX] | **COND*** | Portal-enforced when section is used. Default sentinel: `---Not applicable---` (value `99999999`). Loaded after district selected. Non-India country → leave at sentinel `99999999`. |

#### Not-Applicable Sentinels — Permanent Address (foreign country)

| Field | DOM name | Sentinel Value | Sentinel Label |
|---|---|---|---|
| State | `tenantPermanentState` | `99` | `---Not applicable---` |
| District | `tenantPermanentDistrict` | `99999` | `---Not applicable---` *(must be forced via JS — no matching option exists in DOM by default)* |
| Police Station | `tenantPermanentPoliceStation` | `99999999` | `---Not applicable---` |

---

#### Reference: `STATE_VALUES` — Indian States (for `tenantPermanentState` and `tenantPreviousState`)

This table applies to both the Permanent and Previous address state dropdowns when Country = India.

| Value | Label |
|---|---|
| 1 | ANDAMAN & NICOBAR |
| 2 | ANDHRA PRADESH |
| 3 | ARUNACHAL PRADESH |
| 4 | ASSAM |
| 5 | BIHAR |
| 6 | CHANDIGARH |
| 7 | DAMAN & DIU |
| 8 | DELHI |
| 9 | DADRA & NAGAR HAVELI |
| 10 | GOA |
| 11 | GUJARAT |
| 12 | HIMACHAL PRADESH |
| 13 | HARYANA |
| 14 | JAMMU & KASHMIR |
| 15 | KERALA |
| 16 | KARNATAKA |
| 17 | LAKSHADWEEP |
| 18 | MEGHALAYA |
| 19 | MAHARASHTRA |
| 20 | MANIPUR |
| 21 | MADHYA PRADESH |
| 22 | MIZORAM |
| 23 | NAGALAND |
| 24 | ODISHA |
| 25 | PUNJAB |
| 26 | PUDUCHERRY |
| 27 | RAJASTHAN |
| 28 | SIKKIM |
| 29 | TAMIL NADU |
| 30 | TRIPURA |
| 31 | UTTAR PRADESH |
| 32 | WEST BENGAL |
| 33 | CHHATTISGARH |
| 34 | JHARKHAND |
| 35 | UTTARAKHAND |
| 40 | TELANGANA |
| 41 | LADAKH |

> **Risk flag — non-Delhi Indian state:** `DISTRICT_VALUES` and `POLICE_STATION_VALUES` in `form_filler.py` only cover Delhi districts. If the tenant's permanent or previous address state is an Indian state other than Delhi, the district/station AJAX selection will silently fail — the portal will block submission. This is a pre-existing risk not introduced by the current refactor.
>
> **Out-of-country path works correctly:** When Country is non-India, code must write sentinel values directly to the DOM (State=`99`, District=`99999`, Police Station=`99999999`) rather than attempting dropdown selection. These sentinels are portal-accepted. This path is not currently implemented in `_fill_tenant_address_permanent()`.

---

## TAB 3 — Family Member Information (Tenant's Family)

**Navigation:** Click tab text `"Family Member Information"`
**Readiness signal:** `#rbno` (radio button) becomes visible

> **Context:** This tab is about the **Tenant's family members** who will reside with the tenant at the Tenanted Premises Address. It is not about the owner's family. The question being answered is: does the tenant live alone at the rented property, or do family members also reside there?
>
> **Current automation behaviour:** Code always clicks `#rbno` (Residing alone), which collapses all family fields. If a future use case requires family member details, the fields below become active.

| Portal Label | Element | Type | Required | Code Behaviour |
|---|---|---|---|---|
| Residing with Family | `#rbyes` | Radio | — | Not clicked by code |
| Residing alone | `#rbno` | Radio [AUTO] | — | Code always clicks `#rbno`. All family sub-fields below are hidden after this selection. |
| Relationship with the Tenant | `familyMemberRelationshipWithTenant` | Dropdown | **Yes*** (if `#rbyes`) | Active only when "Residing with Family" selected. Describes how the family member relates to the tenant. |
| Address Verification Document Type | `familyMemberAddressDocuments` | Dropdown | No | Optional document type for the family member's identity. |

---

### 3.1 Dropdown: `familyMemberRelationshipWithTenant` — Relationship with the Tenant *

Active only when "Residing with Family" (`#rbyes`) is selected. Describes the family member's relationship to the **tenant** (not to the owner).

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 21 | Aunt |
| 13 | Brother |
| 14 | Brother-in-Law |
| 30 | Cousin |
| 12 | Daughter |
| 26 | Daughter-in-law |
| 10 | Distant Relative |
| 5 | Father |
| 15 | Father-in-Law |
| 1 | Friend |
| 18 | Grand Father |
| 19 | Grand Mother |
| 7 | Guardian |
| 8 | Husband |
| 27 | Live-in Partner |
| 6 | Mother |
| 16 | Mother-in-Law |
| 3 | Neighbour |
| 25 | Nephew |
| 24 | Niece |
| 2 | Sister |
| 17 | Sister-in-Law |
| 11 | Son |
| 29 | son-in-law |
| 20 | Uncle |
| 9 | Wife |

---

### 3.2 Dropdown: `familyMemberAddressDocuments` — Address Verification Document Type

Null state: `-----------Select-----------` (value `0`)

| Value | Label |
|---|---|
| 8 | Aadhar Card |
| 7 | Any Other |
| 4 | Arms License |
| 2 | Driving License |
| 10 | Electricity Bill |
| 6 | Income Tax (PAN) Card |
| 1 | Passport |
| 3 | Ration Card |
| 9 | Telephone Bill |
| 5 | Voter Card |

> **Note:** Identical values to `tenantAddressDocuments`. Different DOM `name` attribute but same option set.

---

## TAB 4 — Affidavit

**Navigation:** Click tab text `"Affidavit"`
**Readiness signal:** `#allTrue` (checkbox) becomes visible

| Portal Label | Element | Type | Required | Code Behaviour |
|---|---|---|---|---|
| Application Submission Date | *(read-only)* | Read-only | — | Not touched |
| Does the tenant have any criminal record…? | `#hasAnyCriminalRecord1` | Radio [AUTO] | — | Code clicks `#hasAnyCriminalRecord1` = "No" |
| If Yes, Provide Details | *(conditional textarea)* | Textarea | — | Hidden when "No" is selected. Not touched. |
| All the information provided in the form is true | `#allTrue` | Checkbox [AUTO] | **Yes*** | Code calls `check()` then verifies `is_checked()`. Raises RuntimeError if fails. |

---

## SUBMISSION

**Button:** `#submit123`
**Intercept route:** `**/addtenantpgverification.htm` (POST)
**Success signal:** Response body contains `Service Request Number XXXXXXXXXX`

### Pre-submit Validation (in code)

The following fields are validated by `_validate_required_fields_before_submit()` before `#submit123` is clicked:

| Field Name | Type | Display Name |
|---|---|---|
| `ownerFirstName` | Input | Owner first name |
| `ownerLastName` | Input | Owner last name |
| `tenantFirstName` | Input | Tenant first name |
| `tenantLastName` | Input | Tenant last name |
| `ownerOccupation` | Select | Owner occupation |
| `tenantAddressDocuments` | Select | Tenant address document |
| `tenancypurpose` | Select | Purpose of tenancy |

> A value of `""`, `"-1"`, or `"0"` in any Select field above counts as "not filled" and raises `SubmissionValidationError`.

---

## KNOWN GAPS / OUTSTANDING ITEMS

| Item | Status | Impact |
|---|---|---|
| `getpolicestations.htm` exact POST parameter name | **NOT CONFIRMED** | Medium — code currently uses DOM `change` event dispatch which works; direct API parameter name is unknown |
| Station lists for all districts except CENTRAL and EAST | **FROM CODE ONLY** — not live-captured against portal | Medium — `POLICE_STATION_VALUES` values assumed correct but unverified |
| Owner address Country/State — non-India/non-Delhi owner path | **NOT IMPLEMENTED** | High — code leaves Country/State untouched (default India/Delhi). No path exists to write a foreign country or non-Delhi state for owner address. |
| Tenant Permanent/Previous address — non-India country path | **NOT IMPLEMENTED** | High — `_fill_tenant_address_permanent()` has no branch for non-India country. Sentinel values (State=99, District=99999, PS=99999999) are portal-accepted but never written by the current code. |
| Tenant Permanent/Previous address — non-Delhi Indian state | **PRE-EXISTING RISK** | High — district/station AJAX chain will silently fail if state is not DELHI, since `DISTRICT_VALUES` only covers Delhi. |
| Tenant Previous Address — not filled at all | **NOT IMPLEMENTED** | High — portal requires at least one of Previous or Permanent to be filled. Code only fills Permanent. If Permanent data is absent and only Previous exists in payload, submission will fail. |
| `ownerUID` field | **NOT IMPLEMENTED** | Low — optional field, portal does not enforce |
| `tenantOccupation` normalized via `OWNER_OCCUPATIONS.normalize()` | **SHARED ENUM** | Note only — same enum used for both owner and tenant occupation normalization |

---

## APPENDIX A — Complete 216-Country List (Confirmed from Live Log)

This list applies to every Country dropdown in the form that is not portal-locked. That covers:
`ownerCountry` (not currently touched by code), `tenantPreviousCountry`, `tenantPermanentCountry`.

The first entry in every country dropdown is `INDIA` (value `80`) and it is always rendered at the top of the list regardless of alphabetical order.

| Value | Country Label |
|---|---|
| 80 | INDIA *(default, first entry)* |
| 1 | ABU DHABI/DUBAI |
| 2 | AFGHANISTAN |
| 3 | AFRICA |
| 4 | ALBANIA |
| 5 | ALGERIA |
| 6 | ANDORRA |
| 7 | ANGOLA |
| 8 | ARGENTINA |
| 9 | ARMENIA |
| 10 | AUSTRALIA |
| 11 | AUSTRIA |
| 12 | AZERBAIJAN |
| 13 | BAHAMAS |
| 14 | BAHRAIN |
| 15 | BANGLADESH |
| 16 | BARBADOS |
| 17 | BELORUSSIA |
| 18 | BENIN |
| 19 | BELGIUM |
| 20 | BERMUDA |
| 21 | BHUTAN |
| 22 | BOLIVIA |
| 23 | BOSNIA - HERZEGOVINA |
| 24 | BOTSWANA |
| 25 | BRAZIL |
| 26 | BRITISH HONDURAS |
| 27 | BRUNEI |
| 28 | BULGARIA |
| 29 | BURKINA |
| 30 | BURUNDI |
| 31 | CAMBODIA |
| 32 | CAMEROON |
| 33 | CANADA |
| 34 | CAPE VERDE |
| 35 | CENTRAL AFRICAN REPUBLIC |
| 36 | CHAD |
| 37 | CHILE |
| 38 | CHINA |
| 39 | COLOMBIA |
| 40 | COMOROS |
| 41 | CONGO |
| 42 | COSTARICA |
| 43 | CROATIA |
| 44 | CUBA |
| 45 | CYPRUS |
| 46 | CZECH REPUBLIC |
| 47 | DENMARK |
| 48 | DJIBOUTI |
| 49 | DOMINICA |
| 50 | DOMINICAN REPUBLIC |
| 51 | ECUADOR |
| 52 | EGYPT |
| 53 | ELSALVADOR |
| 54 | EQUATORIAL GUINEA |
| 55 | ERITREA |
| 56 | ESTONIA |
| 57 | ETHIOPIA |
| 58 | FALKLAND ISLANDS |
| 59 | FEDERATION OF NIGERIA |
| 60 | FIJI |
| 61 | FINLAND |
| 62 | FRANCE |
| 63 | FRENCH POLYNESIA |
| 64 | GABON |
| 65 | GAMBIA |
| 66 | GEORGIA |
| 67 | GERMANY |
| 68 | GHANA |
| 69 | GREECE |
| 70 | GRENADA |
| 71 | GUATEMALA |
| 72 | GUINEA |
| 73 | GUINEA BISSAU |
| 74 | GUYANA |
| 75 | HAITI |
| 76 | HONDURAS |
| 77 | HONGKONG |
| 78 | HUNGARY |
| 79 | ICELAND |
| 81 | INDONESIA |
| 82 | IRAN |
| 83 | IRAQ |
| 84 | IRELAND (EIRE) |
| 85 | ISRAEL |
| 86 | ITALY |
| 87 | IVORY COAST |
| 88 | JAMAICA |
| 89 | JAPAN |
| 90 | JORDAN |
| 91 | KAZAKHISTAN |
| 92 | KENYA |
| 93 | KIRGIZIA |
| 94 | KIRIBATI |
| 95 | NORTH KOREA |
| 96 | SOUTH KOREA |
| 97 | KUWAIT |
| 98 | LAOS |
| 99 | LATVIA |
| 100 | LEBANON |
| 101 | LESOTHO |
| 102 | LIBERIA |
| 103 | LIBYA |
| 104 | LIECHTENSTEIN |
| 105 | LITHUANIA |
| 106 | LUXEMBOURG |
| 107 | MALAGASY REPUBLIC |
| 108 | MALAWI |
| 109 | MALAYSIA |
| 110 | MALDIVES |
| 111 | MALI |
| 112 | MALTA |
| 113 | MAURITANIA |
| 114 | MAURITIUS |
| 115 | MEXICO |
| 116 | MONACO |
| 117 | MONGOLIA |
| 118 | MOROCCO |
| 119 | MOZAMBIQUE |
| 120 | MYANMAR |
| 121 | NAMIBIA |
| 122 | NAURU |
| 123 | NEPAL |
| 124 | NETHERLANDS |
| 125 | NEW ZEALAND |
| 126 | NICARAGUA |
| 127 | NIGER |
| 128 | NIGERIA |
| 129 | NORWAY |
| 130 | OMAN |
| 131 | PAKISTAN |
| 132 | PANAMA |
| 133 | PAPUA NEW GUINEA |
| 134 | PERU |
| 135 | PHILIPPINES |
| 136 | POLAND |
| 137 | PORTUGAL |
| 138 | QATAR |
| 139 | ROMANIA |
| 140 | RUSSIA |
| 141 | RWANDA |
| 142 | SAUDI ARABIA |
| 143 | SENEGAL |
| 144 | SEYCHELLES |
| 145 | SIERRA LEONE |
| 146 | SINGAPORE |
| 147 | SOMALIA |
| 148 | SOUTH AFRICA |
| 149 | SPAIN |
| 150 | SRI LANKA |
| 151 | SUDAN |
| 152 | SURINAM |
| 153 | SWAZILAND |
| 154 | SWEDEN |
| 155 | SWITZERLAND |
| 156 | SYRIA |
| 157 | TAIWAN |
| 158 | TAJIKISTAN |
| 159 | TANZANIA |
| 160 | THAILAND |
| 161 | TOGO |
| 162 | TRINIDAD & TOBAGO |
| 163 | TUNISIA |
| 164 | TURKEY |
| 165 | TURKMENISTAN |
| 166 | UGANDA |
| 167 | UKRAINE |
| 168 | UNITED ARAB EMIRATES |
| 169 | UNITED KINGDOM |
| 170 | UNITED STATES OF AMERICA |
| 171 | URUGUAY |
| 172 | UZBEKISTAN |
| 173 | VANUATU |
| 174 | VENEZUELA |
| 175 | VIETNAM |
| 176 | WESTERN SAMOA |
| 177 | YEMEN |
| 178 | YUGOSLAVIA |
| 179 | ZAMBIA |
| 180 | ZIMBABWE |
| 181 | ZAIRE |
| 182 | WALLIS & FUTUNA ISLANDS |
| 183 | WEST INDIES |
| 184 | WESTERN AUSTRALIA |
| 185 | YEMAN |
| 186 | YUKON |
| 191 | VANUATU |
| 192 | VATICAN |
| 193 | VENEZUELA |
| 194 | VIETNAM |
| 195 | WALLIS & FUTUNA ISLANDS |
| 196 | WEST INDIES |
| 197 | WESTERN AUSTRALIA |
| 198 | WESTERN SAMOA |
| 199 | YEMAN |
| 200 | YUGOSLAVIA |
| 201 | YUKON |
| 202 | ZAIRE |
| 203 | ZAMBIA |
| 204 | ZIMBABWE |
| 205 | BELARUS |
| 206 | BELIZE |
| 207 | BENIN |
| 208 | BRITAIN |
| 209 | ENGLAND |
| 210 | MACEDONIA |
| 211 | MOLDOVA |
| 212 | MONTENEGRO |
| 213 | SCOTLAND |
| 214 | SERBIA |
| 215 | WALES |
| 216 | UNKNOWN |

> **Note on duplicates in portal data:** The raw log shows some country names appearing twice with different value numbers (e.g. VANUATU at 173 and 191, VENEZUELA at 174 and 193). This is a portal data anomaly — both values exist in the DOM. For automation, always use the lower value number when writing a country programmatically, as it appears earlier in the list and is the canonical entry.

---

## APPENDIX B — Consolidated Field-to-DOM Quick Reference

All fields touched by `form_filler.py`, in fill order, with their DOM `name`/`id`, type, and which payload attribute drives them.

### Tab 1: Owner Information

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `name="ownerFirstName"` | Input | `payload.owner.first_name` | **Yes** |
| `name="ownerMiddleName"` | Input | `payload.owner.middle_name` | No |
| `name="ownerLastName"` | Input | `payload.owner.last_name` | No |
| `name="ownerRelativeName"` | Input | `payload.owner.relative_name` | No |
| `name="ownerOccupation"` | Select | `payload.owner.occupation` | **Yes** |
| `name="ownerRelationType"` | Select | `payload.owner.relation_type` | No |
| `name="ownerMobile1"` | Input | `payload.owner.mobile_no` | No |
| `name="ownerHouseNo"` | Input | `payload.owner.address.house_no` | No |
| `name="ownerStreetName"` | Input | `payload.owner.address.street_name` | No |
| `name="ownerColony"` | Input | `payload.owner.address.colony_locality_area` | No |
| `name="ownerVillage"` | Input | `payload.owner.address.village_town_city` | **Yes** |
| `name="ownerTehsil"` | Input | `payload.owner.address.tehsil_block_mandal` | No |
| `name="ownerPincode"` | Input | `payload.owner.address.pincode` | No |
| `name="ownerDistrict"` | Select [AJAX] | `payload.owner.address.district` → `DISTRICT_VALUES` | **Yes** |
| `name="ownerPoliceStation"` | Select [AJAX] | `payload.owner.address.police_station` → `POLICE_STATION_VALUES` | **Yes** |
| `name="hiddenownerDistrict"` | Hidden | Written by `_select_district_and_station()` | — |
| `name="hiddenownerPStation"` | Hidden | Written by `_select_district_and_station()` | — |

### Tab 2A: Tenant Personal Information

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `name="tenantFirstName"` | Input | `payload.tenant.first_name` | **Yes** |
| `name="tenantMiddleName"` | Input | `payload.tenant.middle_name` | No |
| `name="tenantLastName"` | Input | `payload.tenant.last_name` | No |
| `name="tenantRelativeName"` | Input | `payload.tenant.relative_name` | No |
| `name="tenantGender"` | Select | `payload.tenant.gender` | No |
| `name="tenantOccupation"` | Select | `payload.tenant.occupation` | No |
| `name="tenantRelationType"` | Select | `payload.tenant.relation_type` | No |
| `name="tenantAddressDocuments"` | Select | `payload.tenant.address_verification_doc_type` | **Yes** |
| `name="tenantAddressDocumentsNo"` | Input | `payload.tenant.address_verification_doc_no` | **Yes** |
| `id="tenantVerificationTenantcommonPaneldateOfBirth"` | Date Input | `payload.tenant.dob` (fmt: `dd/MM/yyyy`) | No |
| `id="tenantVerificationTenant.commonPanelAgeYear"` | Input | Calculated from DOB; fallback written directly | No |
| `name="tenancypurpose"` | Select | `payload.tenant.purpose_of_tenancy` | **Yes** |

### Tab 2B: Documents

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `id="fileField2"` | File Upload | `image_bytes` (Aadhaar scan) | **Yes** |
| `id="fileTypeCd2"` | Select [AUTO] | Hardcoded value `"2"` (`ScanPhoto`) | **Yes** |
| `id="filedescriptionId2"` | Input [AUTO] | Hardcoded string `"Aadhaar Card"` | **Yes** |

### Tab 2C-i: Tenanted Premises Address

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `name="tenantPresentHouseNo"` | Input | `payload.tenant.tenanted_address.house_no` | No |
| `name="tenantPresentStreetName"` | Input | `payload.tenant.tenanted_address.street_name` | No |
| `name="tenantPresentColony"` | Input | `payload.tenant.tenanted_address.colony_locality_area` | No |
| `name="tenantPresentVillage"` | Input | `payload.tenant.tenanted_address.village_town_city` | **Yes** |
| `name="tenantPresentTehsil"` | Input | `payload.tenant.tenanted_address.tehsil_block_mandal` | No |
| `name="tenantPresentPincode"` | Input | `payload.tenant.tenanted_address.pincode` | No |
| `name="tenantPresentDistrict"` | Select [STATIC] | `payload.tenant.tenanted_address.district` → `DISTRICT_VALUES` | **Yes** |
| `name="tenantPresentPoliceStation"` | Select [AJAX] | `payload.tenant.tenanted_address.police_station` → `POLICE_STATION_VALUES` | **Yes** |
| `name="hidtenantPrestDistrict"` | Hidden | Written by `_select_district_and_station()` | — |
| `name="hidtenantPresPStation"` | Hidden | Written by `_select_district_and_station()` | — |

### Tab 2C-ii: Previous Address *(not currently implemented)*

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `name="tenantPreviousHouseNo"` | Input | *(no payload mapping yet)* | No |
| `name="tenantPreviousStreetName"` | Input | *(no payload mapping yet)* | No |
| `name="tenantPreviousColony"` | Input | *(no payload mapping yet)* | No |
| `name="tenantPreviousVillage"` | Input | *(no payload mapping yet)* | **COND*** |
| `name="tenantPreviousTehsil"` | Input | *(no payload mapping yet)* | No |
| `name="tenantPreviousPincode"` | Input | *(no payload mapping yet)* | No |
| `name="tenantPreviousCountry"` | Select | *(no payload mapping yet)* | **COND*** |
| `name="tenantPreviousState"` | Select [AJAX] | *(no payload mapping yet)* → `STATE_VALUES` or sentinel `99` | **COND*** |
| `name="tenantPreviousDistrict"` | Select [AJAX] | *(no payload mapping yet)* → `DISTRICT_VALUES` or sentinel `99999` | **COND*** |
| `name="tenantPreviousPoliceStation"` | Select [AJAX] | *(no payload mapping yet)* → `POLICE_STATION_VALUES` or sentinel `99999999` | **COND*** |

### Tab 2C-iii: Permanent Address

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `name="tenantPermanentHouseNo"` | Input | `payload.tenant.address.house_no` | No |
| `name="tenantPermanentStreetName"` | Input | `payload.tenant.address.street_name` | No |
| `name="tenantPermanentColony"` | Input | `payload.tenant.address.colony_locality_area` | No |
| `name="tenantPermanentVillage"` | Input | `payload.tenant.address.village_town_city` | **COND*** |
| `name="tenantPermanentTehsil"` | Input | `payload.tenant.address.tehsil_block_mandal` | No |
| `name="tenantPermanentPincode"` | Input | `payload.tenant.address.pincode` | No |
| `name="tenantPermanentCountry"` | Select | *(not currently mapped in code)* | **COND*** |
| `name="tenantPermanentState"` | Select [AJAX] | `payload.tenant.address.state` → `STATE_VALUES` or sentinel `99` | **COND*** |
| `name="tenantPermanentDistrict"` | Select [AJAX] | `payload.tenant.address.district` → `DISTRICT_VALUES` or sentinel `99999` | **COND*** |
| `name="tenantPermanentPoliceStation"` | Select [AJAX] | `payload.tenant.address.police_station` → `POLICE_STATION_VALUES` or sentinel `99999999` | **COND*** |

### Tab 3: Family Member Information

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `id="rbno"` | Radio [AUTO] | Hardcoded — always "Residing alone" | — |

### Tab 4: Affidavit

| DOM Attribute | Field Type | Payload Source | Mandatory |
|---|---|---|---|
| `id="hasAnyCriminalRecord1"` | Radio [AUTO] | Hardcoded — always "No" | — |
| `id="allTrue"` | Checkbox [AUTO] | Hardcoded — always checked | **Yes** |

### Submission

| DOM Attribute | Purpose |
|---|---|
| `id="submit123"` | Submit button — clicked to trigger form POST |

