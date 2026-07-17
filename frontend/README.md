# Social Media V2 Frontend

- Local product demo: run `./scripts/dev/start_local.sh` from the repository root and open
  `http://127.0.0.1:3010/`.
- Frontend-only development: run `npm run dev`; this expects an API on `127.0.0.1:8000` and does
  not create a session by itself.
- Vite uses `strictPort=true` and does not fall through to another port.
- Run `npm ci` and `npm run build` for a clean production build.
