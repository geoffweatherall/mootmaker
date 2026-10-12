# Mootmaker Privacy Policy — DRAFT

**Not yet published or reviewed by Geoff. Checked against what the system does on 2026-10-12**
(the data model, the handlers, the web and Android apps, and log retention) **— re-check it against
the real code before publishing.** It is written for a future "Sign in with Google", which is not
built yet; remove those parts if it is published before then. Two placeholders need filling in:
contact email, and the effective date. I'm not a lawyer and this isn't legal advice — treat this as
a good-faith accurate draft, not a substitute for legal review if you want real certainty
(particularly if you ever have reason to think GDPR/CCPA-style obligations apply to you).

---

**Effective date**: [DATE]

Mootmaker ("we", "us") is a meeting room booking application. This policy covers the public
Mootmaker site at mootmaker.com, the Mootmaker Android app, and their sign-in options, including "Sign
in with Google."

## What we collect

- **Account information**: your name and email address — either what you provide when you sign up
  directly, or your name/email as provided by Google when you use "Sign in with Google."
- **Password**: only if you sign up directly rather than via Google. It's never stored or seen by
  us in plain text — it's managed entirely by Amazon Cognito, our authentication provider.
- **Booking data you create**: meeting subjects, times, which room you book, who you list as
  attendees (their names, as already known to the system), and your answers to invitations.
- **Preferences**: how you like dates and times shown.
- **A profile photo**, if one is set for you. It is shown to other signed-in users.

## What we don't collect

- We do not access your Gmail, Google Calendar, Google Drive, or any other Google data. "Sign in
  with Google" only ever requests your basic profile (name and email address) to identify your
  account — nothing more.
- We don't use analytics, tracking cookies, or advertising of any kind.
- We don't sell or share your personal information with third parties, for advertising or any
  other purpose.

## Why we collect it

Solely to operate the booking application: to identify you when you sign in, show you your own
meetings, and let administrators manage rooms and people within their organisation's deployment.

## How it's stored

Data is hosted on Amazon Web Services (AWS), transmitted over encrypted (HTTPS) connections, and
authentication is handled by Amazon Cognito, an industry-standard identity platform.

## How long we keep it

We keep your account for as long as it exists. You can delete it yourself at any time, from
Settings, in the web app or the Android app: this deletes your account, your profile and photo, and
your upcoming meetings, and removes you from meetings you were invited to. It cannot be undone.

Meetings are deleted automatically about a month after they take place. Technical logs, which may
include your email address when an account is removed, are kept for 120 days.

## Children

Mootmaker is not directed at, and we do not knowingly collect information from, children.

## Changes to this policy

We may update this policy from time to time; the effective date above will reflect the most recent
change.

## Contact

Questions about this policy or your data: [SUPPORT EMAIL]

---

## Notes for Geoff (delete before publishing)

Things worth knowing beyond "have a privacy policy page," for getting the Google OAuth consent
screen out of Testing mode and staying on the right side of reasonable practice generally:

- **App logo required.** Testing mode doesn't need one; a production consent screen does (Google
  wants a square image, roughly 120x120px minimum). Worth checking `mootmaker/branding/` for
  something suitable, or producing a simple one.
- **Authorized domains + domain verification.** Add `mootmaker.com` as an authorized domain on the
  consent screen, and verify ownership via Google Search Console (a DNS TXT record or hosted HTML
  file — either is easy given you already control the zone via mootmaker-domain/Route53). This
  isn't strictly mandatory for `openid`/`email`/`profile`-only scopes, but it meaningfully reduces
  the chance users see Google's "unverified app" warning screen mid-sign-in, which otherwise hurts
  trust/conversion for no reason.
- **Terms of Service link is optional** on Google's consent screen (only the privacy policy is
  required) — not something you need to produce right now.
- **Scope discipline**: because you're only requesting `openid`/`email`/`profile` (non-sensitive
  scopes), you should **not** need Google's manual verification review at all — that's what makes
  "out of Testing quickly" realistic. That stops being true the moment a *sensitive* scope (like
  Calendar) is added — see the separate note on that question.
- **Keep the policy honest as the app changes** — a policy claiming something the app doesn't
  actually do would look bad to a user, or to Google during any future review.
