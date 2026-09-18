# ig-charity-automation

Fully automated Instagram Reel production for `@kiaraprmd`.

The system generates a text-first 9:16 Reel, automatically chooses copyright-safe emotional music, renders the final MP4 with FFmpeg, uploads it to Cloudinary, then publishes it to Instagram through Buffer. GitHub Actions runs it in the cloud, so no laptop or phone needs to stay online.

## Current visual style

The renderer now uses:

- lighter orange / peach / coral / pink Instagram-style gradients
- Poppins ExtraBold for hooks and CTAs
- Inter Medium for body text
- cleaner spacing and shorter on-screen copy
- no username/link footer at the bottom
- the "link in bio" message only inside the CTA

Fonts are downloaded automatically from Google Fonts and cached by GitHub Actions. DejaVu remains a fallback if the font download is ever unavailable.

## Music

The music library is fully automatic and mood-based. It now includes additional emotional / melancholic / piano tracks, including short emotional piano and a more indie/melancholic instrumental option.

Commercial songs such as Sydney Gish tracks or other copyrighted trending audio are deliberately **not** downloaded and embedded automatically. That would create mute/takedown risk and make the unattended system unreliable. The automated library instead targets the same sad / calm / indie-emotional vibe using reusable music whose source/license is documented in `LICENSES.md`.

## Schedule

Default local posting slots (`Asia/Kolkata`):

- 11:37
- 20:07

Catch-up runs occur after each slot. `state/posted.json` prevents duplicates. If a morning slot is completely missed until the evening window opens, it is dropped rather than dumping two stale Reels close together.

## Truthfulness guard

The copy generator only remixes statements in `config/profile.yml`. It does not invent illnesses, donation totals, emergencies, deadlines, or family circumstances. Keep those approved facts accurate.

## One-time setup

Required GitHub repository secrets:

- `BUFFER_API_KEY`
- `CLOUDINARY_URL`

Buffer channel ID is auto-detected from the configured `@kiaraprmd` handle. `BUFFER_CHANNEL_ID` is only an optional override if auto-detection is ambiguous.

## Preview

Open:

**Actions → Publish Instagram reels → Run workflow → mode = preview**

That renders a Reel and uploads a `reel-preview` artifact. It does **not** contact Buffer or publish to Instagram.

## Live operation

Once the two secrets are configured, scheduled runs:

1. pick the currently due slot
2. generate fresh source-locked copy
3. choose a light Instagram-style visual preset
4. choose a mood-matched music track
5. render 1080×1920 H.264/AAC
6. upload the MP4 to Cloudinary
7. auto-detect the Buffer Instagram channel
8. schedule the Reel
9. record the successful slot in `state/posted.json`

No Stories are generated.
