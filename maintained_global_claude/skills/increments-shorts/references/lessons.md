# Lessons encoded in the code (read when something misbehaves)

- **Gallery tile order can change mid-episode.** Framing infers who is speaking per clip from the faces at the clip's own
  time; never pin one global speaker->tile map. Name tags/pips read `layout_timeline` in `episode.yaml` for the layout at the clip's time.
- **Blur-fill close-ups:** the sharp rect is centred (`dx = (out_w - ow) // 2`). `test_framing.py` guards this.
- **Captions break at every speaker change; minimum display 0.8 s** (a muted tail filler segment may extend a last short word).
- **`validate_clip.py` invariant:** clip `dialogue` must match transcript tokens. If you fix a transcript word, sync the same fix
  into every clip's `dialogue` (and re-run `validate_clip.py`).
- **Long meaningful pauses can be kept deliberately** (split-screen reaction shot): set the segment's visual `locked: true` with a `reason`.
- **A solo-asker shot can be locked** to hide a distracting reaction from the listener (treatment override with `locked: true`).
- **Quote overlays:** prefer ONE fixed highlight on the key sentence for the whole quote, not stepping highlights.
- **Fail loud everywhere.** A red validator is information; fix the input. Never hand-edit a generated output.
- **Real credited media only**; every B-roll file needs a provenance entry.
- **End tag** is added last (`endtag.py`): concatenates a 2.33 s black segment with the alpha tag and its sound after the untouched short.
  Shorts are cut to <= 2:57.6 so the finished file stays under YouTube's 3:00 Shorts limit.
- **Crosstalk:** a stretched backchannel ("Yeah.") aligned across seconds of another speaker's speech stays in the audio, uncaptioned.
