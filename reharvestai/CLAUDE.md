# ReHarvestAI

## Security — Never Leak Secrets
- NEVER hardcode API keys, tokens, or secrets anywhere in code
- All secrets go in `.env.local` (frontend) or `.env` (backend) — never committed
- `NEXT_PUBLIC_MAPBOX_TOKEN` and `NEXT_PUBLIC_API_URL` live in `frontend/.env.local`
- Backend API keys (OpenWeather, Sentinel Hub, etc.) live in `backend/.env`
- Both `.gitignore` files exclude all `.env*` files — do not override this
- If a secret appears in context, do not repeat it in output or commit it
