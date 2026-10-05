"""Stroke-font glyph widths, for placing text so it does not overlap.

The same table drives the symbol builder here and the layout gate of
sbc-development-baseboard (gen/check_pins.py); keep the two copies equal.
"""
import re

# advance of the KiCad stroke font per glyph, in units of the text size: fitted against the
# text extents KiCad writes into its PDF export (2600 words of the baseboard schematic,
# median error 0, 10th/90th percentile -6 % / +16 %); characters it never saw keep a guess
ADV = {"A": 0.88, "B": 0.97, "C": 1.05, "D": 1.02, "E": 0.92, "F": 0.83, "G": 1.02, "H": 1.0, "I": 0.47, "J": 0.92,
       "K": 1.07, "L": 0.79, "M": 1.18, "N": 1.02, "O": 0.99, "P": 0.96, "Q": 1.23, "R": 0.95, "S": 0.96, "T": 0.84,
       "U": 1.0, "V": 0.95, "W": 1.2, "X": 0.97, "Y": 0.89, "Z": 1.2,
       "0": 0.97, "1": 0.86, "2": 0.93, "3": 0.94, "4": 0.94, "5": 0.91, "6": 1.01, "7": 0.94, "8": 0.98, "9": 1.01,
       "a": 1.04, "b": 1.08, "c": 1.05, "d": 1.11, "e": 0.99, "f": 0.75, "g": 1.0, "h": 1.09, "i": 0.53, "j": 0.55,
       "k": 0.89, "l": 0.56, "m": 1.56, "n": 1.05, "o": 1.04, "p": 1.08, "q": 1.08, "r": 0.87, "s": 1.01, "t": 0.72,
       "u": 1.01, "v": 0.84, "w": 1.27, "x": 1.18, "y": 0.9, "z": 0.85,
       "_": 0.86, "/": 0.9, "-": 1.15, "+": 1.14, "(": 0.8, ")": 0.77, ".": 0.56, ",": 0.94, " ": 0.6, "~": 0.95,
       "#": 0.95, "{": 0.5, "}": 0.5, "*": 0.8, "%": 1.0, ":": 0.88, ";": 1.07}

def text_w(s, size):
    s = re.sub(r"~\{([^}]*)\}", r"\1", s)          # overline markup takes no room
    return sum(ADV.get(c, 0.9) for c in s) * size
