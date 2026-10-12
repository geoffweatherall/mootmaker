# Android app problems

Problems specific to the Android app. For sign-in problems, see
[user cannot sign in](user-cannot-sign-in.md); they are the same on both apps.

The app (`com.mootmaker.android`) needs Android 8.0 (API 26) or later. It is distributed as a signed
APK attached to each [GitHub release](https://github.com/geoffweatherall/mootmaker-release/releases/latest),
not through Google Play, so phones do not update it on their own.

## Cannot install

| What happens | Cause | Fix |
|---|---|---|
| The browser or file manager refuses to open the APK | The phone blocks installs from unknown sources | Allow "Install unknown apps" for the browser or file manager, in the phone's settings |
| "App not installed" or "package conflicts with an existing package" over an existing copy | The installed copy was signed with a different key: a debug build, or an acceptance build (signed with a throwaway key) | Uninstall the existing copy first. Its local data (sign-in, cache) is lost; nothing on the server is |
| "There was a problem parsing the package" | A partial download, or Android older than 8.0 | Download again; check the Android version |
| Play Protect warns about an unknown app | Normal for any APK not from Google Play | "Install anyway". Check the file's SHA-256 against the one on the release page if in doubt |

```bash
sha256sum mootmaker-*.apk    # compare with the release notes
```

## Cannot load or cannot connect

On start the app fetches `https://www.<env>.mootmaker.com/mobile-config.json` and keeps the last good
copy, so it can start offline once it has started online once.

| Message | Cause | Fix |
|---|---|---|
| A configuration error on first start | `mobile-config.json` unreachable: no network, the site is down, or the chosen environment does not exist | Check the network, then `curl https://www.mootmaker.com/mobile-config.json`. See [site is down](site-is-down.md) |
| "Couldn't reach Mootmaker" | No network, or the API is down | As above |
| Signed out unexpectedly | The refresh token expired (30 days without use) or was revoked | Sign in again |

## Pointing at the wrong environment

The app talks to `production` unless someone changed it. Tap the version number on the About screen
seven times, then enter an environment name (`test`, or an ephemeral one) or `production`. Testers who
switched to an ephemeral environment that has since been torn down will see configuration errors: switch
back to `production`.

## Errors after an update

The API is released with the web app; phones update only when the user installs a new APK. Every
release checks that the previous release's APK still works against the new API (the n-1 check), but
older APKs are not checked.

| Symptom | Cause | Fix |
|---|---|---|
| "The meeting could not be saved (SomeCode)" | The API returned a refusal this app version does not know | Install the latest APK |
| A screen fails with a GraphQL error about an unknown field | The API removed a field an old app still asks for | Install the latest APK. If the app is the n-1 release, this is a bug: the schema compatibility rules were broken. Open an issue in mootmaker-api |

To see which APK version a phone has: About screen, or Settings → Apps → Mootmaker.

## Live updates stop

Live updates use a WebSocket that Android closes when the app is in the background or the phone locks.
On returning, the app reconnects and refetches what is on screen if it is more than five minutes old.
If a screen still shows something stale, leave it and come back; see
[changes not showing](changes-not-showing.md).

## Reporting a bug

Include the APK version, the Android version and phone model, the environment (About screen), what was
on screen, and the time (with time zone). The app has no crash reporting.
