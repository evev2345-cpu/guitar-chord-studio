"""Shared prompts for all providers; no ground-truth input."""
CANDIDATE_PROMPT = """Find the fretboard of the guitar actively being played.
Return JSON {"bbox": [y_min,x_min,y_max,x_max]} normalized to [0,1000].
Include the entire fretboard from the actual nut to the last metal fret near the body,
including portions covered by the hand. Exclude the headstock and most of the body.
This is only a coarse region for a later close inspection, so leave a small margin."""

CORNER_PROMPT = """Precisely locate the FOUR corners of the FRETBOARD in this enlarged crop.
Use the real nut line as the headstock end, and the LAST METAL FRET WIRE
as the body end. Never use the pickup, pickguard, fingers, wrist or neck shadow.
At each end choose intersections of that SAME transverse line with the two
longitudinal fretboard edges. Follow visible metal fret endpoints and board edges
to infer a hidden intersection; do not follow the outline of the hand.
The top/bottom names refer to STRING SIDES, not image up/down:
nut_top and body_top are on the low-E side;
nut_bottom and body_bottom are on the high-E side.
Return ONLY JSON with coordinates normalized [y,x] in [0,1000] of THIS CROP:
{"nut_top":[y,x],"body_top":[y,x],"body_bottom":[y,x],"nut_bottom":[y,x]}.
Keep both nut corners on the actual nut; do not extend into the first fret space.
Keep both body corners on the same last fret; do not extend onto the pickguard."""
