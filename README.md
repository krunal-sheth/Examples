# Jyotish

A full-stack Vedic astrology application with account authentication, versioned birth profiles, stored Kundli calculations, daily readings, history, and three-point feedback.

## Run locally

Requires Python 3.10+ and no third-party packages.

```bash
python3 server.py
```

Open `http://localhost:8000`. Application data is stored in `data/jyotish.db`.

## Deploy

The included `Dockerfile` runs on any container host. `render.yaml` configures a Render web service with a persistent disk. Connect this repository as a Blueprint in Render, then deploy. Set `DATABASE_PATH` to a persistent volume path on other platforms.

## Security and calculation notes

- Passwords use PBKDF2-SHA256 with unique salts and 310,000 iterations.
- Sessions use random tokens; only their SHA-256 hashes are stored.
- Birth profiles are versioned rather than overwritten.
- The bundled astronomical routine is a deterministic, approximate MVP engine. Before offering paid or professional astrological guidance, replace it with a validated Swiss Ephemeris integration and have calculations reviewed by a qualified Jyotish practitioner.
- Readings are intended for entertainment and personal reflection, not medical, legal, or financial guidance.
