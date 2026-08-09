# Social Media V2 Frontend

- Local product demo: run `npm run dev` from this directory, or
  `./scripts/dev/start_local.sh` from the repository root, and open
  `http://127.0.0.1:3010/`. This starts the V2-only in-memory API on `127.0.0.1:8000`
  and creates a loopback-only development session automatically.
- Frontend-only development: run `npm run dev:frontend`; this expects an API on
  `127.0.0.1:8000` and does not create a session by itself.
- Vite uses `strictPort=true` and does not fall through to another port.
- Run `npm ci` and `npm run build` for a clean production build.
