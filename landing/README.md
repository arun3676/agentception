# Agentception — landing page

A self-contained marketing page. No build step, no dependencies: three files.

```
landing/
  index.html    markup
  styles.css    design tokens mirrored from the app (ui/src/index.css)
  script.js     theme toggle, sticky nav, scroll reveal, CTA wiring
```

## Run locally

```bash
cd landing
python -m http.server 4321
# http://localhost:4321
```

While on `localhost`, every "Open the app" CTA points at `http://localhost:8080`
(the Vite dev server). Anywhere else it uses the production URL.

## Before deploying

Set your production app URL at the top of `script.js`:

```js
var APP_URL = ... : "https://agentception.vercel.app";
```

All `[data-app-link]` anchors are pointed there on load, so there is exactly one
place to change.

## Deploy

Any static host works. On Vercel, create a second project with `landing/` as the
root directory and no build command — it serves the directory as-is.

If you put the landing page on the same domain as the app, add its origin to the
CORS list in `server/app.py`.

## Notes

- Dark and light themes both ship; the toggle persists to `localStorage` and
  falls back to the OS preference.
- The hero panel is a static mockup of the real product UI. It is
  `aria-hidden` — it decorates, it doesn't inform.
- Animations are skipped entirely under `prefers-reduced-motion`.
