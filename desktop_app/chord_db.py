"""Chord Voicings & Guitar Database for Desktop Chord Studio."""

ROOT_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

QUALITIES = [
    'major', 'minor', '7', 'm7', 'maj7', 'sus4', 'dim', 'aug', '6', 'm6', '9', 'm9'
]

STANDARD_VOICINGS = {
    '0:major': {'frets': [-1, 3, 2, 0, 1, 0], 'baseFret': 1},
    '0:minor': {'frets': [-1, 3, 5, 5, 4, 3], 'baseFret': 3},
    '0:7': {'frets': [-1, 3, 2, 3, 1, 0], 'baseFret': 1},
    '0:m7': {'frets': [-1, 3, 5, 3, 4, 3], 'baseFret': 3},
    '0:maj7': {'frets': [-1, 3, 2, 0, 0, 0], 'baseFret': 1},
    '1:major': {'frets': [-1, 4, 6, 6, 6, 4], 'baseFret': 4},
    '1:minor': {'frets': [-1, 4, 6, 6, 5, 4], 'baseFret': 4},
    '2:major': {'frets': [-1, -1, 0, 2, 3, 2], 'baseFret': 1},
    '2:minor': {'frets': [-1, -1, 0, 2, 3, 1], 'baseFret': 1},
    '2:7': {'frets': [-1, -1, 0, 2, 1, 2], 'baseFret': 1},
    '2:m7': {'frets': [-1, -1, 0, 2, 1, 1], 'baseFret': 1},
    '2:sus4': {'frets': [-1, -1, 0, 2, 3, 3], 'baseFret': 1},
    '3:major': {'frets': [-1, 6, 8, 8, 8, 6], 'baseFret': 6},
    '4:major': {'frets': [0, 2, 2, 1, 0, 0], 'baseFret': 1},
    '4:minor': {'frets': [0, 2, 2, 0, 0, 0], 'baseFret': 1},
    '4:7': {'frets': [0, 2, 0, 1, 0, 0], 'baseFret': 1},
    '4:m7': {'frets': [0, 2, 0, 0, 0, 0], 'baseFret': 1},
    '4:maj7': {'frets': [0, 2, 1, 1, 0, 0], 'baseFret': 1},
    '5:major': {'frets': [1, 3, 3, 2, 1, 1], 'baseFret': 1},
    '5:minor': {'frets': [1, 3, 3, 1, 1, 1], 'baseFret': 1},
    '6:major': {'frets': [2, 4, 4, 3, 2, 2], 'baseFret': 2},
    '6:minor': {'frets': [2, 4, 4, 2, 2, 2], 'baseFret': 2},
    '6:m7': {'frets': [2, 4, 2, 2, 2, 2], 'baseFret': 2},
    '7:major': {'frets': [3, 2, 0, 0, 0, 3], 'baseFret': 1},
    '7:minor': {'frets': [3, 5, 5, 3, 3, 3], 'baseFret': 3},
    '7:7': {'frets': [3, 2, 0, 0, 0, 1], 'baseFret': 1},
    '7:m7': {'frets': [3, 5, 3, 3, 3, 3], 'baseFret': 3},
    '7:6': {'frets': [3, 2, 0, 0, 0, 0], 'baseFret': 1},
    '8:major': {'frets': [4, 6, 6, 5, 4, 4], 'baseFret': 4},
    '9:major': {'frets': [-1, 0, 2, 2, 2, 0], 'baseFret': 1},
    '9:minor': {'frets': [-1, 0, 2, 2, 1, 0], 'baseFret': 1},
    '9:7': {'frets': [-1, 0, 2, 0, 2, 0], 'baseFret': 1},
    '9:m7': {'frets': [-1, 0, 2, 0, 1, 0], 'baseFret': 1},
    '10:major': {'frets': [-1, 1, 3, 3, 3, 1], 'baseFret': 1},
    '11:major': {'frets': [-1, 2, 4, 4, 4, 2], 'baseFret': 2},
    '11:minor': {'frets': [-1, 2, 4, 4, 3, 2], 'baseFret': 2},
    '11:7': {'frets': [-1, 2, 1, 2, 0, 2], 'baseFret': 1},
    '11:m7': {'frets': [-1, 2, 4, 2, 3, 2], 'baseFret': 2},
}


def get_chord_voicing(root_pc: int, quality: str):
    """Retrieve 6-string guitar fretting for root_pc (0=C..11=B) and quality."""
    key = f"{root_pc}:{quality}"
    if key in STANDARD_VOICINGS:
        return STANDARD_VOICINGS[key]
    # Movable barre chord approximation
    base = root_pc - 4 if root_pc >= 4 else root_pc + 8
    is_m = 'm' in quality and quality != 'maj7'
    frets = (
        [base, base + 2, base + 2, base, base, base]
        if is_m
        else [base, base + 2, base + 2, base + 1, base, base]
    )
    return {'frets': frets, 'baseFret': max(1, base)}


def parse_symbol(symbol: str):
    """Parse a chord symbol like 'G#m7/D#' or 'B' into root, quality, and bass."""
    if not symbol:
        return None, 'major', None
    parts = symbol.split('/')
    base_sym = parts[0]
    bass = parts[1] if len(parts) > 1 else None

    # Find root
    root = None
    for name in ['C#', 'D#', 'F#', 'G#', 'A#', 'Db', 'Eb', 'Gb', 'Ab', 'Bb',
                 'C', 'D', 'E', 'F', 'G', 'A', 'B']:
        if base_sym.startswith(name):
            root = name
            break
    if not root:
        return None, 'major', bass

    quality = base_sym[len(root):] or 'major'
    return root, quality, bass
