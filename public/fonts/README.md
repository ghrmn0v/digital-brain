# Kariciiniv font files

Drop the licensed font files here and the app will use them automatically.
`src/app/globals.css` already declares the `@font-face` for this family.

Expected file names (the first one found wins):

| File | Format |
| --- | --- |
| `kariciiniv.woff2` | preferred |
| `kariciiniv.woff` | fallback |
| `kariciiniv.ttf` | last resort |

If none of these files exist the browser simply falls through to Geist Sans,
so a missing font never breaks the build.
