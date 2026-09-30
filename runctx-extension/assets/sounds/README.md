# Result Sound

Drop the "result received" notification sound file into this folder.

## Convention
- Required filename: `ding.wav`
- Format: `.wav`
- Suggested length: 0.3s – 1s
- Suggested size: < 500KB

## Changing the sound
Just replace the `ding.wav` file with another one with the SAME NAME. No code change needed.

> Note: the code hard-codes `assets/sounds/ding.wav` (see `utils/sound.js`).
> If you want to use another format (mp3/ogg), you must edit `RESULT_SOUND_PATH` in `utils/sound.js`
> and update `web_accessible_resources` in `manifest.json` to match.

## After adding/removing files
- Reload the extension at `chrome://extensions` (Reload button) so the manifest updates web_accessible_resources.
