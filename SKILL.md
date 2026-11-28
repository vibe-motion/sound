---
name: sound
description: Find and download sound effects from Freesound for videos, using download counts, ratings, descriptions, and licenses to select clips.
allowed-tools: Bash(python3 .claude/skills/sound/scripts/*)
---
Use Freesound for all sound-effect searches and downloads. You can't hear these clips, so lean on what people who did hear them left behind: download counts, ratings, and the uploader's description.

```
S=.claude/skills/sound/scripts/sfx.py
python3 $S freesound "<English query>"     # ↓downloads ★rating(votes) license description
python3 $S freesound "<English query>" --license cc0
python3 $S get <dir> fs:<id>...            # parallel download of searched clips
```
`--urls` on a search adds preview links for the user to audition.

Reading the signals:
- Prefer the most-downloaded clip that fits the cue, and quote the numbers when proposing it. A high rating count beats a high average: ★4.4(380) is stronger evidence than ★4.9(6).
- The Freesound description is the closest thing to listening: "built-in mic" or "made with my mouth" means lo-fi; a named recorder (Zoom, Sound Devices) and a clear source ("cork from a wine bottle") mean you know what you'll get. Reject clips whose description shows a different source than the cue, however popular.
- Freesound licenses: CC0 is free; BY needs a credit (`get` prints it); avoid BY-NC for anything commercial (`--license cc0|by` filters).
- Popularity says nothing about fit: a widely downloaded "thud" can be a 3 s cinematic rumble. Check the duration, and measure with ffmpeg (tail length, where the energy sits) before trusting a top hit. Use `--urls` when the user wants to audition candidates.

- Freesound times out: `python3 .claude/skills/sound/scripts/clash_freesound.py --fix`; if that fails, read references/local-setup.md.
- Freesound caps ~80 KB/s per connection: put all keys in one `get`.
