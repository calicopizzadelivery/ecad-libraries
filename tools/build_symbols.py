#!/usr/bin/env python3
"""Build the calico symbol libraries from pin tables.

Every symbol is a box with named pins, built from a pin table transcribed from
the part's datasheet (each Description says which). The rules the builder
enforces are the house ones from ecad-standards/schematic-style.md: pin names
never overlap (rows are kept clear for the vertical names of top and bottom
pins), reference and value stay off the pins and off each other, 2.54 mm
pitch, 1.27 mm text.

    tools/build_symbols.py            # rewrites symbols/*.kicad_sym
    tools/build_symbols.py --check    # exit 1 if the committed files differ (CI)

The generated files are committed next to this script; this script is the
source of truth and the CI check keeps hand edits out of the output.
"""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glyphs import text_w as glyph_w
from kisym import Sym, dump



def _prop(name, value, at, hide=False, size=1.27, justify=None):
    p = [Sym("property"), name, value, [Sym("at"), at[0], at[1], 0]]
    if hide:
        p.append([Sym("hide"), Sym("yes")])
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        eff.append([Sym("justify"), Sym(justify)])
    p += [[Sym("show_name"), Sym("no")], [Sym("do_not_autoplace"), Sym("no")], eff]
    return p


def _pin(etype, number, name, x, y, angle, length=2.54):
    return [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, angle], [Sym("length"), length],
            [Sym("name"), name, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
            [Sym("number"), number, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]]


def box_symbol(name, left, right, top=(), bottom=(), ref="U", footprint="", description="",
               width=None, pitch=2.54, datasheet="", value_hint=None, keywords=""):
    """left/right/top/bottom: lists of (number, name, etype) in order; None = gap.
    Pins are placed on a 2.54 grid. Returns the symbol node."""
    nl, nr = len(left), len(right)
    nt, nb = len(top), len(bottom)
    h_pins = max(nl, nr)
    H0 = (h_pins + 1) * pitch
    if width is None:
        longest = max([len(p[1]) for p in list(left) + list(right) if p] + [4])
        width = max(20.32, round((longest * 1.3 + 4) / 2.54) * 2.54 * 2 if (nl and nr) else 0, (max(nt, nb) + 1) * pitch)
    # KLC S4.1: every pin on the 2.54 mm grid of the symbol origin. The side pins sit at
    # +-(W/2 + 2.54), so W is a multiple of 5.08; the side rows hang from a grid line, so
    # the row block is shifted up half a pitch when it has an even number of rows
    W = math.ceil(width / 5.08 - 1e-6) * 5.08
    # a top or bottom pin prints its name vertically into the body (1.27 mm text after the
    # 1.016 mm offset; glyph widths from check_pins). Wherever that column meets a side
    # pin's name, the body is extended past the side-pin rows by whole rows until the
    # vertical name clears the side name's box (half height 0.635 mm plus a 0.8 mm gap);
    # the side rows themselves do not move
    OFF, HALF, GAP, SIZE = 0.508, 0.635, 0.8, 1.27     # KLC S3.6: 20 mil pin-name offset
    def name_x(ps, n):                               # x of the n-th top/bottom pin, on the 2.54 grid
        return round(round(-W / 2 + (n + 1) * (W / (len(ps) + 1)), 4) / 2.54) * 2.54
    def side_span(side, p):                          # x extent of a side pin's name, with margin
        w = OFF + glyph_w(p[1], SIZE) + 0.5
        return (-W / 2, -W / 2 + w) if side == "L" else (W / 2 - w, W / 2)
    def clear(ps, from_top):
        need = 0.0
        for n, tp in enumerate(ps):
            if tp is None: continue
            x = name_x(ps, n)
            reach = OFF + glyph_w(tp[1], SIZE) + GAP + HALF
            for side, col in (("L", left), ("R", right)):
                for k, sp in enumerate(col):
                    if sp is None: continue
                    a, b = side_span(side, sp)
                    if b < x - HALF or a > x + HALF: continue
                    dist = (k + 1) * pitch if from_top else (h_pins - k) * pitch   # row from that edge
                    need = max(need, reach - dist)
        return math.ceil(need / pitch) * pitch if need > 0 else 0.0
    top_clear, bottom_clear = clear(top, True), clear(bottom, False)
    x0 = -W / 2
    y0 = math.ceil(H0 / 2 / pitch - 1e-6) * pitch     # top of the side-row block, on the grid (library coords, Y up)
    yt, yb = round(y0 + top_clear, 4), round(y0 - H0 - bottom_clear, 4)   # body top / bottom
    pins = []
    for i, p in enumerate(left):
        if p is None: continue
        y = round(y0 - (i + 1) * pitch, 4)
        pins.append(_pin(p[2], p[0], p[1], round(x0 - 2.54, 4), y, 0))
    for i, p in enumerate(right):
        if p is None: continue
        y = round(y0 - (i + 1) * pitch, 4)
        pins.append(_pin(p[2], p[0], p[1], round(-x0 + 2.54, 4), y, 180))
    for i, p in enumerate(top):
        if p is None: continue
        pins.append(_pin(p[2], p[0], p[1], name_x(top, i), round(yt + 2.54, 4), 270))
    for i, p in enumerate(bottom):
        if p is None: continue
        pins.append(_pin(p[2], p[0], p[1], name_x(bottom, i), round(yb - 2.54, 4), 90))
    stacked = not top and glyph_w(ref + "000", 1.27) + glyph_w(value_hint or name, 1.27) + 2.0 > W   # value_hint: the longest value an instance carries
    body = [Sym("symbol"), f"{name}_0_1",
            [Sym("rectangle"), [Sym("start"), round(x0, 4), yt], [Sym("end"), round(-x0, 4), yb],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]], [Sym("fill"), [Sym("type"), Sym("background")]]]]
    unit = [Sym("symbol"), f"{name}_1_1"] + pins
    node = [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 0.508]], [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            # reference above the top-left corner, value below it (reading leftward): clear of
            # the top and bottom pins, which start further in
            # reference above the top-left corner. Value: above the top-right corner when the top
            # edge is free and both fit on that line; stacked under the reference when the body
            # is too narrow for the two side by side; else below the body, at the left when the
            # bottom edge is busy, at the right otherwise
            # ... and above the top pins' numbers, which run along their stubs, when there are top pins
            _prop("Reference", ref, (round(x0, 4), round(yt + (3.3 if (stacked or top) else 1.27), 4)), justify="left"),
            (_prop("Value", name, (round(x0, 4), round(yt + 1.27, 4)), justify="left") if stacked
             else _prop("Value", name, (round(-x0, 4), round(yt + 1.27, 4)), justify="right") if not top
             else _prop("Value", name, (round(x0, 4), round(yb - 1.27, 4)), justify="right") if nb >= 4
             else _prop("Value", name, (round(-x0, 4), round(yb - 1.27, 4)), justify="right")),
            _prop("Footprint", footprint, (0, 0), hide=True),
            _prop("Datasheet", datasheet, (0, 0), hide=True),
            _prop("Description", description, (0, 0), hide=True),
            _prop("ki_keywords", keywords or KEYWORDS.get(name, ""), (0, 0), hide=True),
            _prop("ki_fp_filters", fp_filter(footprint), (0, 0), hide=True),
            body, unit, [Sym("embedded_fonts"), Sym("no")]]
    return node


def fp_filter(footprint):
    """KLC S5.2: a footprint filter that matches the default footprint and its variants."""
    if not footprint:
        return ""
    return re.sub(r"[-_]", "*", footprint.split(":")[-1]) + "*"


KEYWORDS = {
    "MK64FN1M0VLL12": "NXP Kinetis K64 Cortex-M4F MCU USB ENET",
    "USB2517": "Microchip USB 2.0 hub 7-port",
    "TPS2553DBV": "TI USB power switch current limit",
    "PCA9517A": "NXP I2C bus repeater level translator",
    "TPS54560BDDA": "TI buck step-down converter 5A",
    "JW1FSN": "Panasonic power relay SPDT 10A",
    "USB_A_Stacked2": "USB receptacle double stacked",
}


PI, PO, I, O, B, P, OC, NC = "power_in", "power_out", "input", "output", "bidirectional", "passive", "open_collector", "no_connect"


def k64():
    left = [("13", "VREGIN", PI), ("12", "VOUT33", PO), None,
            ("11", "USB0_DM", B), ("10", "USB0_DP", B), None,            # D- above D+, as on a USBLC6 array
            ("50", "EXTAL0/PTA18", I), ("51", "XTAL0/PTA19", P), ("29", "EXTAL32", P), ("28", "XTAL32", P), None,
            ("52", "RESET_b", I), ("38", "NMI_b/PTA4", I), None,
            ("14", "ADC0_DP1", I), ("15", "ADC0_DM1", I), ("16", "ADC1_DP1", I), ("17", "ADC1_DM1", I),
            ("18", "ADC0_DP0", I), ("19", "ADC0_DM0", I), ("20", "ADC1_DP0", I), ("21", "ADC1_DM0", I),
            ("26", "VREF_OUT", P), ("27", "DAC0_OUT", P)]
    top = [("8", "VDD", PI), ("40", "VDD", PI), ("48", "VDD", PI), ("61", "VDD", PI), ("75", "VDD", PI), ("89", "VDD", PI),
           ("30", "VBAT", PI), ("22", "VDDA", PI), ("23", "VREFH", PI)]
    bottom = [("9", "VSS", PI), ("41", "VSS", PI), ("49", "VSS", PI), ("60", "VSS", PI), ("74", "VSS", PI), ("88", "VSS", PI),
              ("25", "VSSA", PI), ("24", "VREFL", PI)]
    right = [("34", "PTA0/SWD_CLK", B), ("35", "PTA1", B), ("36", "PTA2", B), ("37", "PTA3/SWD_DIO", B),
             ("39", "PTA5/RMII0_RXER", B), ("42", "PTA12/RMII0_RXD1", B), ("43", "PTA13/RMII0_RXD0", B),
             ("44", "PTA14/RMII0_CRS_DV", B), ("45", "PTA15/RMII0_TXEN", B), ("46", "PTA16/RMII0_TXD0", B), ("47", "PTA17/RMII0_TXD1", B), None,
             ("53", "PTB0/RMII0_MDIO", B), ("54", "PTB1/RMII0_MDC", B), ("55", "PTB2/ADC0_SE12", B), ("56", "PTB3/ADC0_SE13", B),
             ("57", "PTB9", B), ("58", "PTB10", B), ("59", "PTB11", B), ("62", "PTB16/UART0_RX", B), ("63", "PTB17/UART0_TX", B),
             ("64", "PTB18", B), ("65", "PTB19", B), ("66", "PTB20", B), ("67", "PTB21", B), ("68", "PTB22", B), ("69", "PTB23", B), None,
             ("70", "PTC0", B), ("71", "PTC1", B), ("72", "PTC2", B), ("73", "PTC3/UART1_RX", B), ("76", "PTC4/UART1_TX", B),
             ("77", "PTC5", B), ("78", "PTC6", B), ("79", "PTC7", B), ("80", "PTC8", B), ("81", "PTC9", B),
             ("82", "PTC10/I2C1_SCL", B), ("83", "PTC11/I2C1_SDA", B), ("84", "PTC12", B), ("85", "PTC13", B), ("86", "PTC14", B),
             ("87", "PTC15", B), ("90", "PTC16", B), ("91", "PTC17", B), ("92", "PTC18", B), None,
             ("93", "PTD0", B), ("94", "PTD1", B), ("95", "PTD2", B), ("96", "PTD3", B), ("97", "PTD4", B), ("98", "PTD5", B),
             ("99", "PTD6", B), ("100", "PTD7", B), None,
             ("1", "PTE0", B), ("2", "PTE1", B), ("3", "PTE2", B), ("4", "PTE3", B), ("5", "PTE4", B), ("6", "PTE5", B), ("7", "PTE6", B),
             ("31", "PTE24/I2C0_SCL", B), ("32", "PTE25/I2C0_SDA", B), ("33", "PTE26", B)]
    return box_symbol("MK64FN1M0VLL12", left, right, top=top, bottom=bottom, ref="U", width=60.96,
                      footprint="Package_QFP:LQFP-100_14x14mm_P0.5mm",
                      description="Kinetis K64, Cortex-M4F 120 MHz, 1 MB flash, 256 KB SRAM, USB FS OTG, 10/100 ENET, LQFP-100. Pinout from K64P144M120SF5 rev 7 table 5.1 (100 LQFP column).",
                      datasheet="https://www.nxp.com/docs/en/data-sheet/K64P144M120SF5.pdf")


def usb2517():
    left = [("58", "USBUP_DM", B), ("59", "USBUP_DP", B), ("44", "VBUS_DET", I), None,     # pairs D- above D+, as on a USBLC6 array
            ("61", "XTAL1/CLKIN", I), ("60", "XTAL2", O), ("43", "RESET_N", I), ("63", "RBIAS", P), ("19", "TEST", I), None,
            ("13", "CFG_SEL2", I), ("42", "HS_IND/CFG_SEL1", B), ("41", "SCL/SMBCLK/CFG_SEL0", B), ("40", "SDA/SMBDATA/NON_REM1", B),
            ("45", "SUSP_IND/LOCAL_PWR/NON_REM0", B)]
    top = [("46", "VDD33", PI), ("24", "VDD33CR", PI), ("64", "VDD33PLL", PI),
           ("5", "VDDA33", PI), ("10", "VDDA33", PI), ("52", "VDDA33", PI), ("57", "VDDA33", PI)]
    bottom = [("25", "VDD18", PO), ("62", "VDD18PLL", PO), ("65", "VSS/EP", PI)]
    right = [("1", "USBDN1_DM", B), ("2", "USBDN1_DP", B), ("3", "USBDN2_DM", B), ("4", "USBDN2_DP", B),
             ("6", "USBDN3_DM/PRT_DIS_M3", B), ("7", "USBDN3_DP/PRT_DIS_P3", B), ("8", "USBDN4_DM", B), ("9", "USBDN4_DP", B),
             ("11", "USBDN5_DM", B), ("12", "USBDN5_DP", B), ("53", "USBDN6_DM", B), ("54", "USBDN6_DP", B),
             ("55", "USBDN7_DM", B), ("56", "USBDN7_DP", B), None,
             ("29", "PRTPWR1", O), ("26", "PRTPWR2", O), ("23", "PRTPWR3", O), ("20", "PRTPWR4", O), ("30", "PRTPWR5", O), ("39", "PRTPWR6", O), ("36", "PRTPWR7", O), None,
             ("28", "OCS1_N", I), ("27", "OCS2_N", I), ("22", "OCS3_N", I), ("21", "OCS4_N", I), ("35", "OCS5_N", I), ("38", "OCS6_N", I), ("37", "OCS7_N", I), None,
             ("51", "LED_A1_N/PRT_SWP1", B), ("49", "LED_A2_N/PRT_SWP2", B), ("47", "LED_A3_N/PRT_SWP3", B), ("33", "LED_A4_N/PRT_SWP4", B),
             ("31", "LED_A5_N/PRT_SWP5", B), ("17", "LED_A6_N/PRT_SWP6", B), ("15", "LED_A7_N/PRT_SWP7", B), None,
             ("50", "LED_B1_N/BOOST0", B), ("48", "LED_B2_N/BOOST1", B), ("34", "LED_B3_N/GANG_EN", B), ("32", "LED_B4_N", B),
             ("18", "LED_B5_N", B), ("16", "LED_B6_N", B), ("14", "LED_B7_N", B)]
    return box_symbol("USB2517", left, right, top=top, bottom=bottom, ref="U", width=68.58,
                      footprint="Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP7.15x7.15mm",
                      description="USB 2.0 Hi-Speed 7-port hub controller, QFN-64. Pinout from DS00001598C Table 5-1.",
                      datasheet="https://ww1.microchip.com/downloads/en/DeviceDoc/USB2517-USB2517i-Data-Sheet-00001598C.pdf")


def tps2553():
    # FAULT two rows above OUT on the right: the switched rail's parts hang down from the OUT
    # row and a label on that row prints above the wire, so the FAULT label needs the gap row
    return box_symbol("TPS2553DBV", [("1", "IN", PI), None, ("3", "EN", I), None, ("5", "ILIM", P)],
                      [("4", "~{FAULT}", OC), None, ("6", "OUT", PO)], bottom=[("2", "GND", PI)], ref="U", width=15.24,
                      footprint="Package_TO_SOT_SMD:SOT-23-6",
                      description="Current-limited USB power switch, EN active high, adjustable limit via ILIM resistor, SOT-23-6. Pinout from TI SLVS841.",
                      datasheet="https://www.ti.com/lit/ds/symlink/tps2553.pdf")


def pca9517a():
    return box_symbol("PCA9517A", [("3", "SDAA", B), ("2", "SCLA", B), None, ("5", "EN", I)],
                      [("6", "SDAB", B), ("7", "SCLB", B)], top=[("1", "VCC(A)", PI), ("8", "VCC(B)", PI)],
                      bottom=[("4", "GND", PI)], ref="U", width=20.32,
                      footprint="Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
                      description="Level-translating I2C bus repeater. Port A 0.9-5.5 V, port B 2.7-5.5 V (0.5 V offset side). EN active high, internal pull-up to VCC(B). Pinout from NXP Table 3.",
                      datasheet="https://www.nxp.com/docs/en/data-sheet/PCA9517A.pdf")


def jw1fsn():
    return box_symbol("JW1FSN", [("1", "COIL+", P), ("8", "COIL-", P)],
                      [("6", "COM", P), ("4", "NO", P), ("2", "NC", P)], ref="K", width=17.78, value_hint="JW1FSN-DC5V",
                      footprint="Relay_THT:Relay_SPDT_Panasonic_JW1_FormC",
                      description="Panasonic 1 Form C power relay, 10 A / 30 VDC, AgSnO2, 5 V 530 mW coil. Pad mapping COM=6 NO=4 NC=2 inferred from the JW datasheet PC-board pattern (pair in one row = NO/NC, single = COM): VERIFY against the Panasonic terminal drawing before fab.",
                      datasheet="https://industrial.panasonic.com/cdbs/www-data/pdf/ADS0000/ADS0000C300.pdf")


def usb_a_stacked():
    """Double-stacked USB-A receptacle as two units, one per port, each drawn as
    its own connector: D-, D+ at the top, VBUS and GND at the bottom, pins on the
    left so the connector faces the sheet edge. Pin numbers follow
    Connector:USB_A_Stacked (1-4 upper port, 5-8 lower port, SH shield)."""
    name = "USB_A_Stacked2"
    W, H = 15.24, 25.4
    x0, y0 = -W / 2, H / 2
    # on the 2.54 grid (KLC S4.1); VBUS sits 12.7 below D+, so the ESD array on the D rows
    # keeps its GND symbol clear of the switched VBUS row drawn under it
    rows = {0: 7.62, 1: 5.08, 6: -7.62, 7: -10.16}
    def unit(u, pins, shield):
        node = [Sym("symbol"), f"{name}_{u}_1",
                [Sym("rectangle"), [Sym("start"), round(x0, 4), round(y0, 4)], [Sym("end"), round(-x0, 4), round(-y0, 4)],
                 [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]], [Sym("fill"), [Sym("type"), Sym("background")]]]]
        for num, pname, row, etype in pins:
            node.append(_pin(etype, num, pname, round(x0 - 2.54, 4), rows[row], 0))
        if shield:
            node.append(_pin(P, "SH", "SHIELD", 0, round(-y0 - 2.54, 4), 90))
        return node
    node = [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 0.508]], [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            # the port name ("USB-A PORT1") and "J4" do not fit side by side on a 15 mm body:
            # reference on the upper line, value on the line just above the body
            _prop("Reference", "J", (round(x0, 4), round(y0 + 3.3, 4)), justify="left"),
            _prop("Value", name, (round(x0, 4), round(y0 + 1.27, 4)), justify="left"),
            _prop("Footprint", "Connector_USB:USB_A_Wuerth_61400826021_Horizontal_Stacked", (0, 0), hide=True),
            _prop("Datasheet", "https://www.we-online.com/components/products/datasheet/61400826021.pdf", (0, 0), hide=True),   # a real link, never "~": KiCad folds "~" to "" in a library but not in an embedded copy, so a multi-unit symbol then mismatches
            _prop("Description", "USB-A receptacle, double stacked, one unit per port", (0, 0), hide=True),
            _prop("ki_keywords", KEYWORDS[name], (0, 0), hide=True),
            _prop("ki_fp_filters", "USB?A*Stacked*", (0, 0), hide=True),
            unit(1, [("2", "D-", 0, B), ("3", "D+", 1, B), ("1", "VBUS", 6, PI), ("4", "GND", 7, PI)], True),
            unit(2, [("6", "D-", 0, B), ("7", "D+", 1, B), ("5", "VBUS", 6, PI), ("8", "GND", 7, PI)], False),
            [Sym("embedded_fonts"), Sym("no")]]
    return node


def tps54560():
    """TPS54560B buck, drawn for the sheet: VIN at the top-left with room below it for
    its input capacitors, the control pins lower, BOOT/SW/FB on the right."""
    return box_symbol("TPS54560BDDA", [("2", "VIN", PI), None, None, None, None, None, ("3", "EN", I), ("4", "RT/CLK", I), None, ("6", "COMP", O)],
                      [("1", "BOOT", P), ("8", "SW", PO), None, None, None, None, None, None, None, ("5", "FB", I)],
                      bottom=[("7", "GND", PI), ("9", "PAD", PI)], ref="U", width=22.86,
                      footprint="Package_SO:HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm",
                      description="4.5-60 V, 5 A step-down converter, HSOP-8. Pinout from TI TPS54560B datasheet pin table.",
                      datasheet="https://www.ti.com/lit/ds/symlink/tps54560b.pdf")


LIBRARIES = {
    "calico-ic": [k64, usb2517, tps2553, pca9517a, tps54560],
    "calico-electromechanical": [usb_a_stacked, jw1fsn],
}


def library_text(builders):
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20251024], [Sym("generator"), "calico-build-symbols"], [Sym("generator_version"), "0.1"]]
    for build in builders:
        lib.append(build())
    return dump(lib) + "\n"


def main(argv):
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "symbols")
    check = "--check" in argv
    stale = 0
    for name, builders in LIBRARIES.items():
        path = os.path.normpath(os.path.join(root, name + ".kicad_sym"))
        text = library_text(builders)
        if check:
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if current != text:
                print(f"{path}: differs from what the builder produces; run tools/build_symbols.py")
                stale += 1
            else:
                print(f"{path}: up to date ({len(builders)} symbols)")
        else:
            open(path, "w", encoding="utf-8").write(text)
            print(f"wrote {path} ({len(builders)} symbols)")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
