#!/usr/bin/env python3
"""Build the calico footprint library from package drawings.

Every footprint is written from the dimensions of a manufacturer drawing, cited in
its description, following the KiCad Library Conventions where the drawing allows
(IPC-style naming, courtyard 0.25 mm beyond the body for packages and 0.5 mm for
connectors, reference on silkscreen, value and a second reference on F.Fab).

    tools/build_footprints.py            # rewrites footprints/calico.pretty/*.kicad_mod
    tools/build_footprints.py --check    # exit 1 if the committed files differ (CI)
"""
import os, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "footprints", "calico.pretty"))
SEED = uuid.UUID("5a3d1c6e-0d1f-4b4a-9f0a-7d3a0c2e5b11")


def _uid(counter):
    counter[0] += 1
    return str(uuid.uuid5(SEED, str(counter[0])))      # stable across builds, so --check is meaningful


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


class FP:
    def __init__(self, name, descr, tags, smd=True):
        self.name, self.descr, self.tags, self.smd = name, descr, tags, smd
        self.items = []
        self.counter = [0]

    def u(self):
        return _uid(self.counter)

    def pad(self, number, shape, at, size, drill=None, layers=None, rot=0, thru=False):
        kind = "thru_hole" if thru else ("np_thru_hole" if drill and number == "" else "smd")
        layers = layers or (["*.Cu", "*.Mask"] if thru else ["F.Cu", "F.Paste", "F.Mask"])
        s = f'  (pad "{number}" {kind} {shape} (at {fmt(at[0])} {fmt(at[1])}{" " + fmt(rot) if rot else ""}) (size {fmt(size[0])} {fmt(size[1])})'
        if drill:
            s += f" (drill {fmt(drill)})"
        if shape == "roundrect":
            s += f" (roundrect_rratio {fmt(round(min(0.25, 0.25 / min(size)) if min(size) < 1 else 0.25, 3))})"
        s += " (layers " + " ".join(f'"{l}"' for l in layers) + f') (uuid "{self.u()}"))'
        self.items.append(s)

    def line(self, a, b, layer, width):
        self.items.append(f'  (fp_line (start {fmt(a[0])} {fmt(a[1])}) (end {fmt(b[0])} {fmt(b[1])}) (stroke (width {fmt(width)}) (type solid)) (layer "{layer}") (uuid "{self.u()}"))')

    def rect(self, a, b, layer, width):
        self.items.append(f'  (fp_rect (start {fmt(a[0])} {fmt(a[1])}) (end {fmt(b[0])} {fmt(b[1])}) (stroke (width {fmt(width)}) (type solid)) (fill no) (layer "{layer}") (uuid "{self.u()}"))')

    def circle(self, c, r, layer, width):
        self.items.append(f'  (fp_circle (center {fmt(c[0])} {fmt(c[1])}) (end {fmt(c[0] + r)} {fmt(c[1])}) (stroke (width {fmt(width)}) (type solid)) (fill no) (layer "{layer}") (uuid "{self.u()}"))')

    def poly(self, pts, layer, width=0.1):
        s = "  (fp_poly (pts " + " ".join(f"(xy {fmt(x)} {fmt(y)})" for x, y in pts) + f') (stroke (width {fmt(width)}) (type solid)) (fill yes) (layer "{layer}") (uuid "{self.u()}"))'
        self.items.append(s)

    def text(self, ref_y, val_y, fab_ref_at=(0, 0), fab_size=1.0):
        eff = "(effects (font (size 1 1) (thickness 0.15)))"
        self.items.insert(0, f'  (property "Reference" "REF**" (at 0 {fmt(ref_y)} 0) (layer "F.SilkS") (uuid "{self.u()}") {eff})')
        self.items.insert(1, f'  (property "Value" "{self.name}" (at 0 {fmt(val_y)} 0) (layer "F.Fab") (uuid "{self.u()}") {eff})')
        self.items.insert(2, f'  (property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{self.u()}") {eff})')
        self.items.insert(3, f'  (property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{self.u()}") {eff})')
        self.items.append(f'  (fp_text user "${{REFERENCE}}" (at {fmt(fab_ref_at[0])} {fmt(fab_ref_at[1])} 0) (layer "F.Fab") (uuid "{self.u()}") (effects (font (size {fmt(fab_size)} {fmt(fab_size)}) (thickness 0.15))))')

    def dump(self):
        head = [f'(footprint "{self.name}"', "  (version 20241229)", '  (generator "calico-build-footprints")', '  (generator_version "10.0")',
                '  (layer "F.Cu")', f'  (descr "{self.descr}")', f'  (tags "{self.tags}")']
        attr = "  (attr smd)" if self.smd else "  (attr through_hole)"
        # the model lives beside the library (3dmodels/calico.3dshapes, Git LFS); the path is relative to the
        # project the way the library tables are, so a project needs no per-machine variable
        model = [f'  (model "${{KIPRJMOD}}/../libs/3dmodels/calico.3dshapes/{self.name}.step"',
                 "    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))"]
        return "\n".join(head + self.items[:4] + [attr] + self.items[4:] + model + ["  (embedded_fonts no)", ")"]) + "\n"


# ----------------------------------------------------------------------------- footprints
def m2_socket_e():
    """TE 2199230-4: M.2 (NGFF) Key E socket, 67 positions, 0.5 mm pitch, 4.2 mm height, SMT right
    angle, from TE customer drawing C-2199230 rev B4 sheet 3 (recommended PCB outline). Origin at the
    connector centre line on the solder-peg axis; the card slot faces +y."""
    f = FP("M.2_Socket_E_TE_2199230-4_67P_P0.5mm_H4.2mm",
           "M.2 (NGFF) Key E socket, 67 positions, 0.5 mm pitch, 4.2 mm height, SMT right angle with two solder pegs. "
           "TE 2199230-4 (15 u-in gold). From TE drawing C-2199230 B4 sheet 3: pads 0.3 x 1.55, odd pins 1-23 and 33-75 in the "
           "slot-side row (y +5.275), even pins 2-22 and 32-74 in the rear row (y -2.275), key E gap at 24-31; pegs 1.1 and 1.6 mm "
           "on the x = +-10 axis; two 1.2 x 2.75 housing tabs at x = +-9.75. https://www.te.com/en/product-2199230-4.html",
           "M.2 NGFF Key E socket connector 67 position")
    # signal pads: odd pins, slot-side row; even pins, rear row. 0.5 mm pitch, the key gap takes pins 24-31
    for k in range(1, 76, 2):
        if 25 <= k <= 31:
            continue
        f.pad(str(k), "roundrect", (round(-9.25 + (k - 1) / 2 * 0.5, 4), -5.275), (0.3, 1.55))
    for k in range(2, 75, 2):
        if 24 <= k <= 30:
            continue
        f.pad(str(k), "roundrect", (round(-9.0 + (k - 2) / 2 * 0.5, 4), 2.275), (0.3, 1.55))
    # housing solder tabs (the drawing's 2X 1.2 x 2.75 pads beside pin 1 and pin 75) and the solder pegs
    for x in (-9.75, 9.75):
        f.pad("MP", "rect", (x, -4.675), (1.2, 2.75))
    f.pad("MP", "circle", (-10.0, 0.0), (1.7, 1.7), drill=1.1, thru=True)
    f.pad("MP", "circle", (10.0, 0.0), (2.2, 2.2), drill=1.6, thru=True)
    # housing: 21.9 wide, 5.85 toward the slot and 2.85 behind the peg axis (KiCad y is down: the slot side is -y)
    x0, x1, yt, yb = -10.95, 10.95, -5.85, 2.85
    f.rect((x0, yt), (x1, yb), "F.Fab", 0.1)
    f.line((x0 + 0.5, yt), (x0, yt + 0.5), "F.Fab", 0.1)                                  # pin-1 corner chamfer
    f.rect((x0 - 0.5, yt - 0.7), (x1 + 0.5, yb + 0.5), "F.CrtYd", 0.05)
    # silkscreen: the housing ends and the rear edge, clear of the pad rows; pin 1 arrow outside the slot-side row
    for sx in (-1, 1):                                                              # ends broken around the solder pegs
        f.line((sx * 11.07, yt - 0.12), (sx * 11.07, -1.6), "F.SilkS", 0.12)
        f.line((sx * 11.07, 1.6), (sx * 11.07, yb + 0.12), "F.SilkS", 0.12)
        f.line((sx * 11.07, yb + 0.12), (sx * 9.6, yb + 0.12), "F.SilkS", 0.12)
    f.line((-11.07, yt - 0.12), (-10.6, yt - 0.12), "F.SilkS", 0.12)
    f.line((11.07, yt - 0.12), (10.6, yt - 0.12), "F.SilkS", 0.12)
    f.circle((-9.25, -6.75), 0.15, "F.SilkS", 0.12)
    f.text(-8.2, 4.1, fab_ref_at=(0, -1.5))
    return f


def fpc_te_1734248_15():
    """TE 1-1734248-5: 15-position 1.0 mm FPC connector, vertical ZIF, SMT, top contact. From the TE
    customer drawing C-1734248 rev E1 (recommended PCB layout): each contact has two solder tails,
    0.6 x 0.95 on the actuator side (y +1.375) and 0.6 x 1.65 on the rear (y -2.075), 1.0 mm pitch;
    circuit 1 at +x. The housing has no fitting nails."""
    f = FP("FPC_TE_1-1734248-5_1x15-1MP_P1.0mm_Vertical",
           "FPC connector, 15 positions, 1.0 mm pitch, vertical, ZIF slide lock, SMT, top contact (TE 1-1734248-5). From TE drawing "
           "C-1734248 E1 recommended PCB layout: two solder pads per contact, 0.6 x 0.95 at y = +1.375 and 0.6 x 1.65 at y = -2.075 "
           "(tails 3.45 mm apart); no fitting nails. Housing 22.4 x 4.6 estimated from the 4.20 end dimension: VERIFY before fab. "
           "https://www.te.com/en/product-1-1734248-5.html",
           "FPC FFC connector 1.0mm vertical ZIF 15")
    for i in range(15):
        x = round(7.0 - i * 1.0, 4)                                      # circuit 1 at +x, as the drawing's top view
        f.pad(str(i + 1), "roundrect", (x, -1.9), (0.6, 0.95))
        f.pad(str(i + 1), "roundrect", (x, 1.55), (0.6, 1.65))
    x0, x1, yt, yb = -11.2, 11.2, -2.3, 2.3
    f.rect((x0, yt), (x1, yb), "F.Fab", 0.1)
    f.line((x1 - 0.5, yt), (x1, yt + 0.5), "F.Fab", 0.1)
    f.rect((x0 - 0.5, yt - 0.5), (x1 + 0.5, yb + 0.5), "F.CrtYd", 0.05)
    for sx in (-1, 1):
        f.line((sx * 11.32, yt - 0.12), (sx * 11.32, yb + 0.12), "F.SilkS", 0.12)
        f.line((sx * 11.32, yt - 0.12), (sx * 7.6, yt - 0.12), "F.SilkS", 0.12)
        f.line((sx * 11.32, yb + 0.12), (sx * 7.6, yb + 0.12), "F.SilkS", 0.12)
    f.circle((7.0, -2.95), 0.15, "F.SilkS", 0.12)
    f.text(-3.7, 3.7, fab_ref_at=(0, 0))
    return f


def _dfn8_3p3(name, descr, tags, lead, ep, ep_at=(0.0, 0.0), merged_bottom=False):
    """8-lead 3.3 x 3.3 mm DFN, 0.65 mm pitch, pins 1-4 along -y (pin 1 at -x), 5-8 along +y, exposed pad."""
    f = FP(name, descr, tags)
    xs = [-0.975, -0.325, 0.325, 0.975]
    lw, lh, ly = lead
    for i, x in enumerate(xs):
        f.pad(str(i + 1), "roundrect", (x, ly), (lw, lh))
    for i, x in enumerate(reversed(xs)):
        f.pad(str(5 + i), "roundrect", (x, -ly), (lw, lh))
    f.pad("5" if merged_bottom else "9", "rect", ep_at, ep, layers=["F.Cu", "F.Mask"])
    f.items.append(f'  (pad "" smd rect (at {fmt(ep_at[0])} {fmt(ep_at[1])}) (size {fmt(round(ep[0] * 0.6, 3))} {fmt(round(ep[1] * 0.6, 3))}) (layers "F.Paste") (uuid "{f.u()}"))')
    b = 1.65
    f.rect((-b, -b), (b, b), "F.Fab", 0.1)
    f.line((-b + 0.5, b), (-b, b - 0.5), "F.Fab", 0.1)          # pin 1 at -x, +y (KiCad y down: the pin-1 row is at +y)
    f.rect((-b - 0.25, -b - 0.25), (b + 0.25, b + 0.25), "F.CrtYd", 0.05)
    for sy in (-1, 1):
        f.line((-1.4, sy * 1.77), (1.4, sy * 1.77), "F.SilkS", 0.12)
    f.circle((-1.5, 2.15), 0.15, "F.SilkS", 0.12)
    f.text(-2.6, 2.7, fab_ref_at=(0, 0), fab_size=0.6)
    return f


def onsemi_wdfn8():
    return _dfn8_3p3("onsemi_WDFN8-1EP_3.3x3.3mm_P0.65mm",
                     "onsemi WDFN8 3.3x3.3 0.65P (case 511AB), from the soldering footprint on the NTTFS4C25N datasheet: 8 leads 0.42 x 0.66 "
                     "at 0.65 mm pitch, overall 3.46 x 3.60; the drain leads 5-8 and the exposed pad are one copper (the drawing's stepped "
                     "pad is drawn as a 2.37 x 2.30 rectangle merged with leads 5-8): VERIFY against case 511AB before fab. "
                     "https://www.onsemi.com/pdf/datasheet/nttfs4c25n-d.pdf",
                     "WDFN DFN 3.3x3.3 0.65 u8FL MOSFET", lead=(0.42, 0.66, 1.47), ep=(2.37, 2.30), ep_at=(0.0, -0.45), merged_bottom=True)


def st_powerflat8():
    return _dfn8_3p3("ST_PowerFLAT-8_3.3x3.3mm_P0.65mm",
                     "ST PowerFLAT 3.3x3.3 (8 leads), from the STL6P3LLH6 datasheet Table 8 / Figure 5: body 3.30 x 3.30, lead width b 0.23-0.38, "
                     "lead length L 0.30-0.50, pitch 0.65, exposed pad D2 2.50-2.75 x E2 1.25-1.50; pads 0.40 x 0.85 with 0.35 mm toe, exposed "
                     "pad 2.75 x 1.50 at the body centre (the drawing offsets it 0.33 mm toward pins 5-8: VERIFY before fab). "
                     "https://www.st.com/resource/en/datasheet/stl6p3llh6.pdf",
                     "PowerFLAT DFN 3.3x3.3 0.65 MOSFET", lead=(0.40, 0.85, 1.40), ep=(2.75, 1.50))


FOOTPRINTS = [m2_socket_e, fpc_te_1734248_15, onsemi_wdfn8, st_powerflat8]


def main(argv):
    check = "--check" in argv
    os.makedirs(LIB, exist_ok=True)
    stale = 0
    for build in FOOTPRINTS:
        f = build()
        path = os.path.join(LIB, f.name + ".kicad_mod")
        text = f.dump()
        if check:
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if current != text:
                print(f"{path}: differs from what the builder produces; run tools/build_footprints.py"); stale += 1
            else:
                print(f"{path}: up to date")
        else:
            open(path, "w", encoding="utf-8").write(text); print(f"wrote {path}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
