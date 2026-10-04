# Appearance preferences

System is the default. The browser resolves it using the device’s light/dark
preference and responds to changes while the page is open. Choosing Light or
Dark overrides device mode until System is selected again.

Authenticated GET/PUT `/auth/me/preferences` reads or saves only
`theme_preference` (`system`, `light`, `dark`) for the current user and organization.
Device mode changes never send writes. The additive users column is created on
normal backend startup; existing accounts default to System.

The existing next-themes provider keeps `data-theme` styling and uses separate
localStorage keys for each account and for anonymous visitors. On login the
account preference loads from FastAPI. A manual selection made while loading
takes priority. Saves are serialized and rapid selections coalesce to the latest
choice. Account changes abort outstanding frontend requests and discard queued
saves. Failed saves retain the browser choice and show a retry action; refreshing
loads the last successfully saved account preference.

Other devices load the saved preference on their next page load. There is no
real-time cross-device push. System can resolve differently on each device.

Implementation was not tested or deployed; verification remains with the owner.
