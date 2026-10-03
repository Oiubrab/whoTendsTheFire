# whoTendsTheFire UI

React + TypeScript + Vite + Tailwind. Talks to `server.py`'s `/api/*`
endpoints; has no backend of its own.

```
npm install
npm run dev     # dev server at :5173, proxies /api to a bridge on :8420
                # (set BRIDGE_PORT to point at a different one)
npm run build   # writes dist/, which server.py serves directly
```

`tendfire` (see `~/.zshrc`) rebuilds automatically when `src/` is newer
than `dist/index.html`, so day to day you only need `npm run dev` while
actively changing the UI.

See `docs/` at the repo root for the design plan this was built from.
