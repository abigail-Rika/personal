# Anya look mechanics

Anya is a humanoid pixel companion holding a small round green companion against the front of her torso. The lower body, shoes, skirt hem, and the held companion's attachment point stay anchored. The gaze leads with the original green eyes and eyelids; the head and pink hair follow with a restrained turn, while the black cat-ear bows follow the head and the upper torso makes only a small counter-follow-through. Preserve the original eye construction: whole eye/eyelid shapes participate together, with no replacement googly eyes or detached pupils. The round companion stays hand-held and body-attached, becoming slightly more side-on or partially occluded as Anya turns rather than sliding independently.

Cardinal pose families, in viewer/screen coordinates:

- `000` up: chin and eye line lift toward 12 o'clock; more underside of fringe is visible, eyelids open upward, hair and bows lag slightly; companion remains front-attached.
- `090` screen-right: nose and pupils move to the image right, face turns right, right cheek becomes more prominent and the far cheek/eye is slightly occluded; the companion follows the torso with a small rightward side reveal.
- `180` down: chin tucks toward 6 o'clock, eyelids lower and the eye line drops; top of hair and bows become more visible, with the companion still attached and stable.
- `270` screen-left: nose and pupils move to the image left, face turns left, left cheek becomes more prominent and the far cheek/eye is slightly occluded; the companion follows with the opposing side reveal.

Intermediate directions interpolate evenly through these four families in the fixed clockwise order. Each 22.5-degree step uses a small, consistent change in eye/eyelid direction, head turn, hair/bow follow-through, and companion side visibility. Keep the feet/base registration and body scale constant; do not rotate, skew, or affine-tilt the whole sprite.
