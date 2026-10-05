"""S-expression parsing and KiCad symbol-library access.

Minimal and dependency-free. Parses .kicad_sym files into nested lists,
serialises them back in KiCad's layout, and resolves a symbol (following
`extends`) into a flattened definition ready to embed in a schematic's
lib_symbols section, with its pin geometry available for wiring.
"""
import math, os, re, glob

KICAD_SYMBOLS = "/usr/share/kicad/symbols"


# ----------------------------------------------------------------------------- s-expr
class Sym(str):
    """A bare token (unquoted) as opposed to a quoted string."""
    __slots__ = ()


def parse(text):
    tokens = _tokenize(text)
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]; pos += 1
        if tok == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(read())
            pos += 1
            return lst
        if tok.startswith('"'):
            return _unescape(tok[1:-1])
        return Sym(tok)

    out = read()
    return out


def _tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            toks.append(c); i += 1
        elif c == '"':
            j = i + 1
            while True:
                if text[j] == "\\":
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            toks.append(text[i:j + 1]); i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n()":
                j += 1
            toks.append(text[i:j]); i = j
    return toks


def _unescape(s):
    return s.replace('\\"', '"').replace("\\\\", "\\")


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def fmt(v):
    """Numbers as KiCad writes them: no trailing zeros, '0' for zero."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return v


def dump(node, indent=0):
    """Serialise a nested list in KiCad's one-child-per-line style."""
    pad = "\t" * indent
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return pad + str(node)
        if isinstance(node, (int, float)):
            return pad + fmt(node)
        return pad + '"' + _escape(str(node)) + '"'
    # head + inline scalars, then nested lists on their own lines
    head = []
    rest = []
    seen_list = False
    for el in node:
        if isinstance(el, list):
            seen_list = True
            rest.append(el)
        elif not seen_list:
            head.append(el)
        else:
            rest.append(el)
    parts = [str(h) if isinstance(h, Sym) else (fmt(h) if isinstance(h, (int, float)) else '"' + _escape(str(h)) + '"') for h in head]
    line = pad + "(" + " ".join(parts)
    if not rest:
        return line + ")"
    out = [line]
    for el in rest:
        out.append(dump(el, indent + 1))
    out.append(pad + ")")
    return "\n".join(out)


def find(node, key):
    """First child list whose head is `key`."""
    for el in node:
        if isinstance(el, list) and el and el[0] == key:
            return el
    return None


def find_all(node, key):
    return [el for el in node if isinstance(el, list) and el and el[0] == key]


def prop(node, name):
    for el in find_all(node, "property"):
        if el[1] == name:
            return el
    return None


# ----------------------------------------------------------------------------- libraries
_lib_cache = {}


def load_lib(libname):
    if libname in _lib_cache:
        return _lib_cache[libname]
    path = os.path.join(KICAD_SYMBOLS, libname + ".kicad_sym")
    tree = parse(open(path, encoding="utf-8").read())
    syms = {}
    for el in tree:
        if isinstance(el, list) and el and el[0] == "symbol":
            syms[el[1]] = el
    _lib_cache[libname] = syms
    return syms


def get_symbol(libname, name, project_lib=None):
    """Return a flattened copy of the symbol as a nested list, with its name
    rewritten to `libname:name` (how schematics store embedded symbols)."""
    if project_lib is not None and libname in project_lib:
        syms = project_lib[libname]
    else:
        syms = load_lib(libname)
    if name not in syms:
        raise KeyError(f"{libname}:{name} not in library")
    node = _deepcopy(syms[name])
    ext = find(node, "extends")
    if ext is not None:
        parent = _deepcopy(syms[ext[1]])
        # child keeps its own properties; everything else comes from the parent
        child_props = {p[1]: p for p in find_all(node, "property")}
        merged = [parent[0], node[1]]
        for el in parent[2:]:
            if isinstance(el, list) and el and el[0] == "property":
                if el[1] in child_props:
                    merged.append(child_props.pop(el[1]))
                else:
                    merged.append(el)
            elif isinstance(el, list) and el and el[0] == "extends":
                continue
            elif isinstance(el, list) and el and el[0] == "symbol":
                # sub-unit names carry the parent's name; rename to the child's
                sub = _deepcopy(el)
                sub[1] = sub[1].replace(ext[1], node[1], 1)
                merged.append(sub)
            else:
                merged.append(el)
        for p in child_props.values():
            merged.append(p)
        node = merged
    # rename to lib-qualified
    node[1] = f"{libname}:{name}"      # sub-units keep the bare name: "R_0_1"
    return node


def _deepcopy(n):
    if isinstance(n, list):
        return [_deepcopy(x) for x in n]
    return n


# ----------------------------------------------------------------------------- pins
class Pin:
    __slots__ = ("number", "name", "etype", "x", "y", "angle", "length", "unit")

    def __init__(self, number, name, etype, x, y, angle, length, unit):
        self.number, self.name, self.etype = number, name, etype
        self.x, self.y, self.angle, self.length, self.unit = x, y, angle, length, unit

    def __repr__(self):
        return f"Pin({self.number} {self.name} {self.etype} at {self.x},{self.y} r{self.angle})"


def pins_of(symnode):
    """All pins of a (flattened) symbol, library coordinates (Y up)."""
    out = []
    for sub in find_all(symnode, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        unit = int(m.group(1)) if m else 0
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            length = find(p, "length")
            name = find(p, "name")
            number = find(p, "number")
            out.append(Pin(number[1], name[1], str(p[1]), float(at[1]), float(at[2]),
                           int(float(at[3])) if len(at) > 3 else 0,
                           float(length[1]) if length else 0.0, unit))
    return out


def transform(x, y, X, Y, rot, mirror=None):
    """Library point (Y up) -> schematic point for an instance at (X, Y, rot)."""
    dx, dy = x, -y                       # flip to screen (Y down)
    if mirror == "x":
        dy = -dy
    elif mirror == "y":
        dx = -dx
    r = rot % 360
    if r == 90:
        dx, dy = dy, -dx
    elif r == 180:
        dx, dy = -dx, -dy
    elif r == 270:
        dx, dy = -dy, dx
    return (round(X + dx, 4), round(Y + dy, 4))


def pin_direction(angle, rot, mirror=None):
    """Which way a pin *points away from the body* on screen, after placement.
    Library pin angle: 0 = pin drawn to the right of its connection point
    (connection point is the outer end), i.e. the body is to the right, the
    pin points left on screen. Returns 'L','R','U','D' = direction from body
    to connection point on screen."""
    # in library coords (Y up), angle 0 means the line goes from (x,y) toward +x:
    # body is at +x, so the connection point is on the body's LEFT.
    base = {0: "L", 180: "R", 90: "D", 270: "U"}[angle % 360]  # 90: line goes +y (up) so point is BELOW body
    if mirror == "y":
        base = {"L": "R", "R": "L"}.get(base, base)
    if mirror == "x":
        base = {"U": "D", "D": "U"}.get(base, base)
    order = ["R", "U", "L", "D"]           # counter-clockwise on screen
    i = order.index(base)
    steps = (rot % 360) // 90
    return order[(i + steps) % 4]
