# Project Overview

**Last updated:** 2026-04-04
**Status:** Active development

---

## What is this project?

This is a **Telegram bot** that automates the process of registering a tenant with the Delhi Police.

In Delhi, property owners are legally required to register any tenant staying at their property with the local police station. This is done through the Delhi Police CCTNS portal (a government website). Filling out this form manually is slow, repetitive, and error-prone.

This bot lets an owner start a chat on Telegram, upload photos of the Aadhaar cards for both the owner and the tenant, review the extracted details, and have the form submitted to the government portal automatically — without ever visiting the website themselves.

---

## Who uses it?

**Primary user:** The property owner (or their representative), who initiates the bot on Telegram.

The owner provides:
- Their own Aadhaar card photo
- The tenant's Aadhaar card photo
- The address of the rented property (typed as free text)

---

## How does the flow work? (Step by step)

```
1. Owner opens Telegram and sends /start
2. Bot asks for consent → owner agrees
3. Owner uploads photo(s) of their Aadhaar card
4. Bot reads the card using AI (Groq vision) and extracts name, address, Aadhaar number, etc.
5. Bot shows owner a review screen — owner can edit any field that was read incorrectly
6. Owner confirms their details
7. Bot asks for the address of the rented property (typed as text)
8. Bot shows a review screen for the tenanted address — owner can edit
9. Owner confirms the tenanted address
10. Owner uploads photo(s) of the tenant's Aadhaar card
11. Bot reads the tenant's card the same way
12. Bot shows tenant details review screen — owner can edit
13. Owner confirms tenant details
14. Bot shows the tenant's permanent address review screen — owner can edit
15. Owner confirms everything → bot submits the form to the Delhi Police portal
16. Bot sends a PDF confirmation back to the owner on Telegram
```

---

## What technology is used?

| Piece | What it does |
|-------|-------------|
| **Telegram Bot (aiogram)** | The chat interface the owner interacts with |
| **Groq API (vision model)** | Reads Aadhaar card photos and extracts structured information |
| **Playwright** | Controls a real browser to log in and fill the government portal |
| **Python** | The language everything is written in |
| **SQLite** | Stores analytics (how long sessions take, how many edits, etc.) |

---

## What does the bot NOT do?

- It does not store Aadhaar numbers permanently (only for the duration of a session)
- It does not support registering multiple tenants in one session
- It does not currently support owners or tenants whose address is outside India
- It does not support tenant previous address (only permanent address is filled on the portal)
- It does not send reminders or follow up after submission

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Initial creation. Consolidated from codebase audit and constraint review. |
