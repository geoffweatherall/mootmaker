# Mootmaker — Feature Overview

Mootmaker is a meeting room booking system: book a room in seconds, see what's free at a glance, and keep every person's schedule in one place. This document lists what an end user (and their IT admin) can actually do with it, written for a non-technical reader — it's the source list for marketing/brochure copy, not a technical spec.

Each customer runs their own independent deployment of Mootmaker, with its own data, its own sign-in, and its own web address. Nothing here is shared between customers.

## Why Mootmaker

- **Book a room in seconds** — one screen, no multi-step wizard, no phoning around to check if a room is free.
- **Never double-book** — the system won't let two meetings clash in the same room, and won't let a meeting overflow a room's capacity.
- **Self-service from day one** — staff create their own accounts and reset their own passwords; nobody has to raise an IT ticket just to sign in.
- **Looks and feels modern** — a clean, custom-branded interface with light and dark mode, not a dated internal tool.
- **Your own private instance** — a dedicated deployment per customer, with your own web address, not a shared multi-tenant system.
- **Cost-efficient to run** — cloud infrastructure that scales with actual usage, not a fixed monthly server bill.

## Book Meetings in Seconds

- Booking a room is one simple form — subject, who's organising, who's attending, the date, the time, and the room — filled in on a single screen with nothing to click through first.
- A **"Suggest a room"** button does the searching for you: it finds the smallest room that's free at the chosen time and fits everyone, and fills it in automatically. Don't like the suggestion? Press it again for the next best option.
- The system actively protects against common booking mistakes before they happen: it won't let a room be double-booked, won't let a meeting exceed the room's capacity, and won't let the person organising a meeting accidentally also be listed as one of its attendees.
- If something can't be booked, every problem is reported back at once — no back-and-forth of fixing one issue only to discover another.

## See Room Availability at a Glance

- A daily view lays out every room side by side, with existing meetings shown as blocks across the part of the day they occupy — so it's immediately obvious which rooms are free right now, and which are booked out.
- Jump to any date, past or future, with one click.
- Each room is colour-coded for quick scanning, so a regular user starts to recognise "their" meeting room at a glance.

## Everyone's Schedule, One Click Away

- Every person gets their own calendar view — a full six-week wall calendar showing every meeting they're organising or attending, at a glance.
- Find anyone's calendar instantly with a type-ahead search, and share the link with a colleague so they're looking at exactly the same view.
- The home page greets each user with **"Today"** and **"Tomorrow"** agenda lists — their own next meetings, front and centre, the moment they sign in.

## Self-Service Onboarding — No IT Bottleneck

- Anyone can create their own account in under a minute: name, email, password — no administrator approval needed to get started.
- A short email verification step confirms the account before it can be used, keeping sign-ups genuine without adding friction.
- Forgotten passwords are no longer a support call: users request a reset code by email and set a new password themselves, any time, day or night.
- Password-reset requests never reveal whether an email address actually has an account — a small but genuine privacy protection built in from the start.
- Prospective customers don't have to take our word for it — a live, instantly-accessible demo login lets anyone try the real product before signing up for their own.

## Simple, Centralised Administration

- One Settings screen covers everything an administrator needs: managing the list of rooms (name and capacity) and the list of people, with nothing extra to learn.
- Guests and visitors who don't need their own login can still be added as a person and booked into meetings on their behalf — useful for external visitors, contractors, or anyone who shouldn't need an account of their own.
- Rename anyone at any time; the new name appears everywhere instantly — meeting lists, calendars, everywhere their name is shown.
- Administrator access itself is granted outside the product, not through a screen — a deliberate security choice so no user can ever promote themselves to admin, by accident or otherwise.

## Designed to Be Loved, Not Endured

- A clean, modern interface built on Google's Material Design language, with its own custom colour palette, typography, and hand-crafted illustrations — not an off-the-shelf, generic-looking internal tool.
- Automatically follows the user's own light or dark mode preference, so it looks right on their device without them having to think about it.
- Fully responsive — works just as well on a phone or tablet in a corridor as it does at a desk.
- Clear feedback at every step: visible loading indicators while data is fetched, disabled/spinning buttons that prevent accidental double-submits, and plain-English messages whenever something needs fixing.

## Enterprise-Grade Security, Zero Hassle

- Sign-in is built on Amazon Cognito, an industry-standard identity platform — passwords are never sent or stored in the clear, and sessions use short-lived, automatically-refreshed tokens rather than a permanent credential that could be stolen and reused indefinitely.
- Role-based access from the start: every account is a standard user or an administrator, and only administrators can manage rooms and people.
- Every rule is enforced on the server, not just hidden in the interface — so the system stays correct and secure even against a client trying to bypass the on-screen restrictions.

## Your Own Dedicated Deployment

- Every customer gets a fully independent deployment — its own database, its own user accounts, its own sign-in, and its own custom web address (e.g. `yourcompany.mootmaker.com`) — never a shared, multi-tenant system with someone else's data alongside yours.
- Built on cloud infrastructure that bills for actual use rather than fixed server capacity, so cost tracks real usage instead of a flat monthly fee regardless of how much (or little) it's used.
- A new deployment can be stood up quickly, without months of implementation — fast time-to-value from day one.

## On the Roadmap

Mootmaker is under active development. Planned enhancements include:

- Recurring meetings (e.g. a standing weekly slot).
- Editing or cancelling a meeting after it's booked.
- Meeting reminders and confirmation notifications.
- Signing in with an existing Google account.
- A native mobile app alongside the web app.

## See It In Action

The fastest way to understand Mootmaker is to try it — book a room, browse the daily availability view, and see a personal calendar fill in, all in a live, no-commitment demo.
