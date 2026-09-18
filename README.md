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

The included library uses CC0-style sources listed in `LICENSES.md`. The project deliberately does not scrape or download copyrighted Spotify/Instagram/TikTok songs.

## One-time setup

Only **two GitHub repository secrets** are required:

- `BUFFER_API_KEY`
- `CLOUDINARY_URL`

The Buffer channel ID is auto-detected from the `@kiaraprmd` Instagram handle configured in `config/profile.yml`. If the Buffer account has multiple Instagram channels and auto-detection is ever ambiguous, `BUFFER_CHANNEL_ID` can optionally be added as an override.

### Buffer

1. Create/log in to Buffer.
2. Connect the Instagram account `@kiaraprmd` as an Instagram professional channel.
3. In Buffer, open **Settings → API**.
4. Create a personal API key and copy it.
5. In GitHub, add it as the repository secret `BUFFER_API_KEY`.

### Cloudinary

1. Create/log in to Cloudinary.
2. Open **Settings → API Keys**.
3. Copy the full **API environment variable** beginning with `cloudinary://`.
4. In GitHub, add that entire value as the repository secret `CLOUDINARY_URL`.

### GitHub

In this repository open:

`Settings → Secrets and variables → Actions → New repository secret`

Add the two secrets above. Never paste either secret into source files, Issues, commits, or chat screenshots.

After those two secrets are set, the scheduled workflow handles generation, music, rendering, media hosting, Buffer publishing, retries, and state tracking by itself.

## Run flow

1. Check whether today's first or second slot is due.
2. Skip if that slot is already recorded.
3. Build fresh copy from approved facts + rotating hooks/story angles/CTAs.
4. Pick a visual theme.
5. Download/cache the licensed music library if needed.
6. Select a mood-matched track.
7. Render a 1080×1920, 30 fps, 12-second H.264/AAC Reel.
8. Upload the MP4 to Cloudinary.
9. Auto-detect the connected `@kiaraprmd` Buffer channel.
10. Schedule it through Buffer as an Instagram Reel shared to feed.
11. Record the successful slot in `state/posted.json`.

## Safe test

The CI workflow performs an offline render test automatically on every push.

For a no-post preview, open **Actions → Publish Instagram reels → Run workflow**, leave **mode = preview**, and run it. The workflow renders a Reel and uploads a `reel-preview` artifact; it does not contact Buffer or publish anything.

After both secrets are present and the facts in `config/profile.yml` have been checked, you can optionally run the same workflow with **mode = live-due**. That mode behaves like the scheduler and can publish whichever normal slot is currently due.

## Files

- `config/profile.yml` — schedule, approved facts, CTA and hashtags
- `config/music.yml` — mood-tagged licensed music sources
- `app/content.py` — copy/story variation engine
- `app/music.py` — downloader/cache/selector
- `app/render.py` — 9:16 design renderer + FFmpeg encoder
- `app/publish.py` — Cloudinary + Buffer API integration
- `app/state.py` — due-slot and duplicate prevention
- `.github/workflows/post.yml` — unattended cloud scheduler
