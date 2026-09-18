# ig-charity-automation

Fully automated Instagram Reel production for `@kiaraprmd`.

The system generates a text-first 9:16 Reel, automatically downloads/chooses matching licensed music, renders the final MP4 with FFmpeg, uploads it to Cloudinary, then publishes it to Instagram through Buffer. GitHub Actions runs it in the cloud, so no laptop or phone needs to stay online.

## Schedule

Default local posting slots (`Asia/Kolkata`):

- 11:37
- 20:07

The workflow also has catch-up checks later in each window. `state/posted.json` makes the process idempotent, so catch-up runs do nothing after a slot succeeds.

## Reused logic from AutoTube Lab

`autotube-lab` is a much heavier research/TTS/Remotion pipeline. This project reuses the parts that fit this job:

- source-locked content generation instead of inventing facts
- deterministic slot/state logic
- mood-based audio selection
- FFmpeg media rendering/mixing
- retry/fail-closed publishing boundaries

The local LLM, TTS, Playwright, GPU stack, Remotion scenes, and YouTube publisher are intentionally not copied because a static-text charity Reel does not need them.

## Truthfulness guard

The copy generator can only remix the statements in `config/profile.yml`. It does **not** invent new illnesses, donation totals, emergencies, deadlines, or family circumstances.

The current fact block was carried over from the reference copy supplied for this page. Keep it accurate; edit or remove any line that is not true.

## Music

Tracks are automatically downloaded from the licensed sources in `config/music.yml`, cached by GitHub Actions, and embedded into the rendered MP4. Selection is mood-based and avoids the previous track when possible.

The included library uses CC0/public-domain-style sources listed in `LICENSES.md`. The project deliberately does not scrape or download copyrighted Spotify/Instagram/TikTok songs.

## One-time setup

Connect `@kiaraprmd` to Buffer as an Instagram **Creator or Business** account and create a Buffer API key. Create a free Cloudinary account.

In this repository go to:

`Settings → Secrets and variables → Actions → New repository secret`

Add:

- `BUFFER_API_KEY`
- `BUFFER_CHANNEL_ID`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

After those five secrets are set, the scheduled workflow handles generation, music, rendering, upload, publishing, retries, and state tracking by itself.

## Run flow

1. Check whether today's first or second slot is due.
2. Skip if that slot is already recorded.
3. Build fresh copy from approved facts + rotating hooks/story angles/CTAs.
4. Pick a visual theme.
5. Download/cache the licensed music library if needed.
6. Select a mood-matched track.
7. Render a 1080×1920, 30 fps, 12-second H.264/AAC Reel.
8. Upload the MP4 to Cloudinary.
9. Send it to Buffer as an Instagram Reel shared to feed.
10. Record the successful slot in `state/posted.json`.

## Optional local smoke test

```bash
python -m pip install -e ".[dev]"
pytest -q
python -m app.main --render-only --force-slot 2026-09-18-1
```

`--render-only` never publishes.

## Files

- `config/profile.yml` — schedule, approved facts, CTA and hashtags
- `config/music.yml` — mood-tagged licensed music sources
- `app/content.py` — copy/story variation engine
- `app/music.py` — downloader/cache/selector
- `app/render.py` — 9:16 design renderer + FFmpeg encoder
- `app/publish.py` — Cloudinary + Buffer API integration
- `app/state.py` — due-slot and duplicate prevention
- `.github/workflows/post.yml` — unattended cloud scheduler
