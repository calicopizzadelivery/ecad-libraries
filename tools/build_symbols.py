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


def _pin(etype, number, name, x, y, angle, length=2.54, hide=False):
    node = [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, angle], [Sym("length"), length]]
    if hide:
        node.append([Sym("hide"), Sym("yes")])                       # KLC S4.6: a no-connect pin is invisible
    return node + [[Sym("name"), name, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
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
        pins.append(_pin(p[2], p[0], p[1], round(x0 - 2.54, 4), y, 0, hide=p[2] == NC))
    for i, p in enumerate(right):
        if p is None: continue
        y = round(y0 - (i + 1) * pitch, 4)
        pins.append(_pin(p[2], p[0], p[1], round(-x0 + 2.54, 4), y, 180, hide=p[2] == NC))
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


def units_symbol(name, units, ref="U", footprint="", description="", datasheet="", value_hint=None, keywords=""):
    """A multi-unit box symbol: units = [dict(left, right, top, bottom, width)] in unit order.
    Each unit gets its own rectangle and pins under `name_<u>_1`; the fields come from unit 1."""
    nodes = [box_symbol(name, u.get("left", []), u.get("right", []), u.get("top", ()), u.get("bottom", ()), ref=ref,
                        footprint=footprint, description=description, width=u.get("width"), datasheet=datasheet,
                        value_hint=value_hint, keywords=keywords)
             for u in units]
    head = [c for c in nodes[0] if not (isinstance(c, list) and c and c[0] in (Sym("symbol"), Sym("embedded_fonts")))]
    subs = []
    for u, n in enumerate(nodes, start=1):
        body = pins = None
        for c in n:
            if isinstance(c, list) and c and c[0] == Sym("symbol"):
                if c[1].endswith("_0_1"): body = c
                elif c[1].endswith("_1_1"): pins = c
        subs.append([Sym("symbol"), f"{name}_{u}_1"] + body[2:] + pins[2:])
    return head + subs + [[Sym("embedded_fonts"), Sym("no")]]


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
    # mythtv-porg (Jetson Nano carrier)
    "EFM8SB10F2G": "Silicon Labs Sleepy Bee 8051 MCU QFN20 supervisor",
    "GS7116S5-ADJ": "Green Solution LDO adjustable 500mA SOT23-5",
    "MP2152": "MPS buck step-down converter 2A QFN",
    "TPS53015": "TI D-CAP synchronous buck controller VSSOP-10",
    "STUSB4531": "ST USB-C PD sink controller standalone QFN-16",
    "NCP301LSN20T1": "onsemi voltage detector reset supervisor 2.0V",
    "CYUSB3304": "Infineon Cypress EZ-USB HX3 USB 3.0 hub 4-port",
    "AP22811": "Diodes load switch current limit 2A SOT-25",
    "APL3552": "Anpec load switch adjustable current limit SOT23-5",
    "GS7616SC": "Green Solution load switch small SOT-363",
    "TPD4E02B04DQA": "TI ESD protection array 4-channel HDMI USB3",
    "2N7002DW": "Diodes dual N-channel MOSFET SOT-363 level shifter",
    "Jetson_Nano_SODIMM": "NVIDIA Jetson Nano module SO-DIMM 260 socket",
    "USB3_A_Stacked2": "USB 3.0 receptacle double stacked SuperSpeed",
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
    # upstream pair D- above D+ (the order on a USBLC6 array), then VBUS_DET with clear rows
    # around it so the upstream connector's lower pins have no hub lane on their rows; the
    # crystal pins last, so the clock source hangs below everything else on that side
    left = [("58", "USBUP_DM", B), ("59", "USBUP_DP", B), None, None, ("44", "VBUS_DET", I), None, None, None,
            ("43", "RESET_N", I), ("63", "RBIAS", P), ("19", "TEST", I), None,
            ("13", "CFG_SEL2", I), ("42", "HS_IND/CFG_SEL1", B), ("41", "SCL/SMBCLK/CFG_SEL0", B), ("40", "SDA/SMBDATA/NON_REM1", B),
            ("45", "SUSP_IND/LOCAL_PWR/NON_REM0", B), None, ("61", "XTAL1/CLKIN", I), ("60", "XTAL2", O)]
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


# ----------------------------------------------------------------------------- mythtv-porg
def _conv(rows):
    """Old-generator rows (number, name, etype) -> box_symbol rows; None stays a gap."""
    return [None if r is None else (str(r[0]), r[1], r[2]) for r in rows]


# --- Jetson Nano SO-DIMM, five units (Nano PDG Table 2-2 names; pin usage is a sheet matter) ---
SODIMM_UNITS = [{'h': 86.36,
  'left': [('237', 'POWER_EN', 'input'), ('239', 'SYS_RESET*', 'output'), ('233', 'SHUTDOWN_REQ*', 'open_collector'), ('240', 'SLEEP/WAKE*', 'input'),
           ('214', 'FORCE_RECOVERY*', 'input'), ('178', 'MOD_SLEEP*', 'output'), ('235', 'PMIC_BBAT', 'passive'), ('210', 'CLK_32K_OUT', 'output'),
           ('127', 'GPIO04', 'bidirectional'), None, ('99', 'UART0_TXD', 'output'), ('101', 'UART0_RXD', 'input'), ('103', 'UART0_RTS*', 'output'),
           ('105', 'UART0_CTS*', 'input'), None, ('203', 'UART1_TXD', 'output'), ('205', 'UART1_RXD', 'input'), ('207', 'UART1_RTS*', 'output'),
           ('209', 'UART1_CTS*', 'input'), None, ('236', 'UART2_TXD', 'output'), ('238', 'UART2_RXD', 'input')],
  'name': 'control',
  'right': [('185', 'I2C0_SCL', 'bidirectional'), ('187', 'I2C0_SDA', 'bidirectional'), ('189', 'I2C1_SCL', 'bidirectional'),
            ('191', 'I2C1_SDA', 'bidirectional'), ('232', 'I2C2_SCL', 'bidirectional'), ('234', 'I2C2_SDA', 'bidirectional'),
            ('213', 'CAM_I2C_SCL', 'bidirectional'), ('215', 'CAM_I2C_SDA', 'bidirectional'), None, ('87', 'GPIO00', 'bidirectional'),
            ('118', 'GPIO01', 'bidirectional'), ('124', 'GPIO02', 'bidirectional'), ('126', 'GPIO03', 'bidirectional'),
            ('128', 'GPIO05', 'bidirectional'), ('130', 'GPIO06', 'bidirectional'), ('206', 'GPIO07', 'bidirectional'),
            ('208', 'GPIO08', 'bidirectional'), ('211', 'GPIO09', 'bidirectional'), ('212', 'GPIO10', 'bidirectional'),
            ('216', 'GPIO11', 'bidirectional'), ('218', 'GPIO12', 'bidirectional'), ('228', 'GPIO13', 'bidirectional'),
            ('230', 'GPIO14', 'bidirectional'), None, ('114', 'CAM0_PWDN', 'output'), ('116', 'CAM0_MCLK', 'output'), ('120', 'CAM1_PWDN', 'output'),
            ('122', 'CAM1_MCLK', 'output'), None, ('143', 'RSVD', 'no_connect'), ('145', 'RSVD', 'no_connect')],
  'w': 35.56},
 {'h': 78.74,
  'left': [('109', 'USB0_D_N', 'bidirectional'), ('111', 'USB0_D_P', 'bidirectional'), None, ('115', 'USB1_D_N', 'bidirectional'),
           ('117', 'USB1_D_P', 'bidirectional'), None, ('121', 'USB2_D_N', 'bidirectional'), ('123', 'USB2_D_P', 'bidirectional'), None,
           ('161', 'USBSS_RX_N', 'input'), ('163', 'USBSS_RX_P', 'input'), ('166', 'USBSS_TX_N', 'output'), ('168', 'USBSS_TX_P', 'output'), None,
           ('184', 'GBE_MDI0_N', 'bidirectional'), ('186', 'GBE_MDI0_P', 'bidirectional'), ('190', 'GBE_MDI1_N', 'bidirectional'),
           ('192', 'GBE_MDI1_P', 'bidirectional'), ('196', 'GBE_MDI2_N', 'bidirectional'), ('198', 'GBE_MDI2_P', 'bidirectional'),
           ('202', 'GBE_MDI3_N', 'bidirectional'), ('204', 'GBE_MDI3_P', 'bidirectional'), ('188', 'GBE_LED_LINK', 'output'),
           ('194', 'GBE_LED_ACT', 'output')],
  'name': 'usb-gbe-spi-i2s-sdmmc',
  'right': [('89', 'SPI0_MOSI', 'output'), ('91', 'SPI0_SCK', 'output'), ('93', 'SPI0_MISO', 'input'), ('95', 'SPI0_CS0*', 'output'),
            ('97', 'SPI0_CS1*', 'output'), None, ('104', 'SPI1_MOSI', 'output'), ('106', 'SPI1_SCK', 'output'), ('108', 'SPI1_MISO', 'input'),
            ('110', 'SPI1_CS0*', 'output'), ('112', 'SPI1_CS1*', 'output'), None, ('193', 'I2S0_DOUT', 'output'), ('195', 'I2S0_DIN', 'input'),
            ('197', 'I2S0_FS', 'bidirectional'), ('199', 'I2S0_SCLK', 'bidirectional'), None, ('220', 'I2S1_DOUT', 'output'),
            ('222', 'I2S1_DIN', 'input'), ('224', 'I2S1_FS', 'bidirectional'), ('226', 'I2S1_SCLK', 'bidirectional'), None,
            ('219', 'SDMMC_DAT0', 'bidirectional'), ('221', 'SDMMC_DAT1', 'bidirectional'), ('223', 'SDMMC_DAT2', 'bidirectional'),
            ('225', 'SDMMC_DAT3', 'bidirectional'), ('227', 'SDMMC_CMD', 'bidirectional'), ('229', 'SDMMC_CLK', 'output')],
  'w': 33.02},
 {'h': 86.36,
  'left': [('63', 'DP1_TXD0_N', 'output'), ('65', 'DP1_TXD0_P', 'output'), ('69', 'DP1_TXD1_N', 'output'), ('71', 'DP1_TXD1_P', 'output'),
           ('75', 'DP1_TXD2_N', 'output'), ('77', 'DP1_TXD2_P', 'output'), ('81', 'DP1_TXD3_N', 'output'), ('83', 'DP1_TXD3_P', 'output'),
           ('98', 'DP1_AUX_N', 'bidirectional'), ('100', 'DP1_AUX_P', 'bidirectional'), ('96', 'DP1_HPD', 'input'),
           ('94', 'HDMI_CEC', 'bidirectional'), None, ('39', 'DP0_TXD0_N', 'output'), ('41', 'DP0_TXD0_P', 'output'), ('45', 'DP0_TXD1_N', 'output'),
           ('47', 'DP0_TXD1_P', 'output'), ('51', 'DP0_TXD2_N', 'output'), ('53', 'DP0_TXD2_P', 'output'), ('57', 'DP0_TXD3_N', 'output'),
           ('59', 'DP0_TXD3_P', 'output'), ('90', 'DP0_AUX_N', 'bidirectional'), ('92', 'DP0_AUX_P', 'bidirectional'), ('88', 'DP0_HPD', 'input'),
           None, ('70', 'DSI_D0_N', 'output'), ('72', 'DSI_D0_P', 'output'), ('82', 'DSI_D1_N', 'output'), ('84', 'DSI_D1_P', 'output'),
           ('76', 'DSI_CLK_N', 'output'), ('78', 'DSI_CLK_P', 'output')],
  'name': 'video-pcie',
  'right': [('131', 'PCIE0_RX0_N', 'input'), ('133', 'PCIE0_RX0_P', 'input'), ('134', 'PCIE0_TX0_N', 'output'), ('136', 'PCIE0_TX0_P', 'output'),
            ('137', 'PCIE0_RX1_N', 'input'), ('139', 'PCIE0_RX1_P', 'input'), ('140', 'PCIE0_TX1_N', 'output'), ('142', 'PCIE0_TX1_P', 'output'),
            ('149', 'PCIE0_RX2_N', 'input'), ('151', 'PCIE0_RX2_P', 'input'), ('148', 'PCIE0_TX2_N', 'output'), ('150', 'PCIE0_TX2_P', 'output'),
            ('155', 'PCIE0_RX3_N', 'input'), ('157', 'PCIE0_RX3_P', 'input'), ('154', 'PCIE0_TX3_N', 'output'), ('156', 'PCIE0_TX3_P', 'output'),
            ('160', 'PCIE0_CLK_N', 'output'), ('162', 'PCIE0_CLK_P', 'output'), ('179', 'PCIE_WAKE*', 'input'), ('180', 'PCIE0_CLKREQ*', 'input'),
            ('181', 'PCIE0_RST*', 'output'), None, ('167', 'RSVD', 'no_connect'), ('169', 'RSVD', 'no_connect'), ('172', 'RSVD', 'no_connect'),
            ('174', 'RSVD', 'no_connect'), ('173', 'RSVD', 'no_connect'), ('175', 'RSVD', 'no_connect'), ('182', 'RSVD', 'no_connect'),
            ('183', 'RSVD', 'no_connect')],
  'w': 33.02},
 {'h': 55.88,
  'left': [('4', 'CSI0_D0_N', 'input'), ('6', 'CSI0_D0_P', 'input'), ('16', 'CSI0_D1_N', 'input'), ('18', 'CSI0_D1_P', 'input'),
           ('10', 'CSI0_CLK_N', 'input'), ('12', 'CSI0_CLK_P', 'input'), None, ('3', 'CSI1_D0_N', 'input'), ('5', 'CSI1_D0_P', 'input'),
           ('15', 'CSI1_D1_N', 'input'), ('17', 'CSI1_D1_P', 'input'), ('9', 'RSVD', 'no_connect'), ('11', 'RSVD', 'no_connect'), None,
           ('22', 'CSI2_D0_N', 'input'), ('24', 'CSI2_D0_P', 'input'), ('34', 'CSI2_D1_N', 'input'), ('36', 'CSI2_D1_P', 'input'),
           ('28', 'CSI2_CLK_N', 'input'), ('30', 'CSI2_CLK_P', 'input')],
  'name': 'csi',
  'right': [('21', 'CSI3_D0_N', 'input'), ('23', 'CSI3_D0_P', 'input'), ('33', 'CSI3_D1_N', 'input'), ('35', 'CSI3_D1_P', 'input'),
            ('27', 'CSI3_CLK_N', 'input'), ('29', 'CSI3_CLK_P', 'input'), None, ('46', 'CSI4_D0_N', 'input'), ('48', 'CSI4_D0_P', 'input'),
            ('58', 'CSI4_D1_N', 'input'), ('60', 'CSI4_D1_P', 'input'), ('40', 'CSI4_D2_N', 'input'), ('42', 'CSI4_D2_P', 'input'),
            ('64', 'CSI4_D3_N', 'input'), ('66', 'CSI4_D3_P', 'input'), ('52', 'CSI4_CLK_N', 'input'), ('54', 'CSI4_CLK_P', 'input')],
  'w': 30.48},
 {'h': 96.52,
  'left': [('1', 'GND', 'power_in'), ('2', 'GND', 'power_in'), ('7', 'GND', 'power_in'), ('8', 'GND', 'power_in'), ('13', 'GND', 'power_in'),
           ('14', 'GND', 'power_in'), ('19', 'GND', 'power_in'), ('20', 'GND', 'power_in'), ('25', 'GND', 'power_in'), ('26', 'GND', 'power_in'),
           ('31', 'GND', 'power_in'), ('32', 'GND', 'power_in'), ('37', 'GND', 'power_in'), ('38', 'GND', 'power_in'), ('43', 'GND', 'power_in'),
           ('44', 'GND', 'power_in'), ('49', 'GND', 'power_in'), ('50', 'GND', 'power_in'), ('55', 'GND', 'power_in'), ('56', 'GND', 'power_in'),
           ('61', 'GND', 'power_in'), ('62', 'GND', 'power_in'), ('67', 'GND', 'power_in'), ('68', 'GND', 'power_in'), ('73', 'GND', 'power_in'),
           ('74', 'GND', 'power_in'), ('79', 'GND', 'power_in'), ('80', 'GND', 'power_in'), ('85', 'GND', 'power_in'), ('86', 'GND', 'power_in'),
           ('102', 'GND', 'power_in'), ('107', 'GND', 'power_in'), ('113', 'GND', 'power_in'), ('119', 'GND', 'power_in')],
  'name': 'power',
  'right': [('125', 'GND', 'power_in'), ('129', 'GND', 'power_in'), ('132', 'GND', 'power_in'), ('135', 'GND', 'power_in'),
            ('138', 'GND', 'power_in'), ('141', 'GND', 'power_in'), ('144', 'GND', 'power_in'), ('146', 'GND', 'power_in'),
            ('147', 'GND', 'power_in'), ('152', 'GND', 'power_in'), ('153', 'GND', 'power_in'), ('158', 'GND', 'power_in'),
            ('159', 'GND', 'power_in'), ('164', 'GND', 'power_in'), ('165', 'GND', 'power_in'), ('170', 'GND', 'power_in'),
            ('171', 'GND', 'power_in'), ('176', 'GND', 'power_in'), ('177', 'GND', 'power_in'), ('200', 'GND', 'power_in'),
            ('201', 'GND', 'power_in'), ('217', 'GND', 'power_in'), ('231', 'GND', 'power_in'), ('241', 'GND', 'power_in'),
            ('242', 'GND', 'power_in'), ('243', 'GND', 'power_in'), ('244', 'GND', 'power_in'), ('245', 'GND', 'power_in'),
            ('246', 'GND', 'power_in'), ('247', 'GND', 'power_in'), ('248', 'GND', 'power_in'), ('249', 'GND', 'power_in'),
            ('250', 'GND', 'power_in'), ('MP', 'MP', 'passive')],
  'top': [('251', 'VDD_IN', 'power_in'), ('252', 'VDD_IN', 'power_in'), ('253', 'VDD_IN', 'power_in'), ('254', 'VDD_IN', 'power_in'),
          ('255', 'VDD_IN', 'power_in'), ('256', 'VDD_IN', 'power_in'), ('257', 'VDD_IN', 'power_in'), ('258', 'VDD_IN', 'power_in'),
          ('259', 'VDD_IN', 'power_in'), ('260', 'VDD_IN', 'power_in')],
  'w': 30.48}]


def jetson_nano_sodimm():
    units = [dict(left=_conv(u.get("left", [])), right=_conv(u.get("right", [])), top=_conv(u.get("top", ())),
                  bottom=_conv(u.get("bottom", ())), width=u["w"]) for u in SODIMM_UNITS]
    return units_symbol("Jetson_Nano_SODIMM", units, ref="J", footprint="Connector_PCBEdge:SODIMM-260_DDR4_H4.0-5.2_OrientationStd_Socket",
                        description="NVIDIA Jetson Nano module (P3448-0000 / -0002) in a 260-pin DDR4 SO-DIMM socket, five units: control / USB-GbE-SPI-I2S-SDMMC / video-PCIe / CSI / power. Pin names and numbers from the Jetson Nano Product Design Guide DG-09502-001 v2.4 Table 2-2; pins 9/11 and 167-183 are RSVD there.",
                        datasheet="https://developer.nvidia.com/embedded/dlc/jetson-nano-product-design-guide", value_hint="Jetson Nano")


def efm8():
    return box_symbol("EFM8SB10F2G",
                      [("5", "RST#/C2CK", B), ("6", "P2.7/C2D", B), ("7", "P1.7", B), ("8", "P1.6", B), ("9", "P1.5", B), ("10", "P1.3", B), ("11", "P1.2", B)],
                      [("2", "P0.0", B), ("1", "P0.1", B), ("20", "P0.2", B), ("19", "P0.3", B), ("18", "P0.4", B), ("17", "P0.5", B), ("16", "P0.6", B), ("15", "P0.7", B), ("14", "P1.0", B), ("13", "P1.1", B)],
                      top=[("4", "VDD", PI)], bottom=[("3", "GND", PI), ("12", "GND", PI), ("21", "EP", PI)], ref="U", width=25.4,
                      footprint="Package_DFN_QFN:QFN-20-1EP_3x3mm_P0.4mm_EP1.65x1.65mm",
                      description="Silicon Labs Sleepy Bee 8051 MCU, 2 kB flash, QFN20. Pin numbers from the EFM8SB1 datasheet pin definitions table (QFN20 column); used as the Jetson power-button supervisor, after NVIDIA P3509 U18.",
                      datasheet="https://www.silabs.com/documents/public/data-sheets/efm8sb1-datasheet.pdf")


def gs7116():
    return box_symbol("GS7116S5-ADJ", [("1", "IN", PI), ("3", "EN", I)], [("5", "OUT", PO), ("4", "ADJ", I)], bottom=[("2", "GND", PI)],
                      ref="U", width=15.24, footprint="Package_TO_SOT_SMD:SOT-23-5", value_hint="GS7116S5-ADJ-R",
                      description="Green Solution 500 mA adjustable LDO, 0.8 V reference, SOT23-5. Pin order from the GS7116 datasheet pin configuration (SOT23-5); NVIDIA P3509 U6, the 3V3_AO rail. No manufacturer-hosted datasheet: the link is a mirror.",
                      datasheet="https://datasheetspdf.com/pdf/1095893/GStek/GS7116/1")


def mp2152():
    return box_symbol("MP2152", [("3", "IN", PI), ("4", "EN", I)], [("2", "SW", O), ("6", "OUT", PO), ("5", "FB", I)], bottom=[("1", "GND", PI)],
                      ref="U", width=15.24, footprint="Package_DFN_QFN:DFN-6-1EP_2x2mm_P0.65mm_EP1x1.6mm", value_hint="MP2152GQFU",
                      description="MPS 2 A 5.5 V synchronous buck, 1.1 MHz, QFN-6 2x2. Pin numbers from the MP2152 datasheet pin functions table (QFN-6 (2x2mm)); NVIDIA P3509 U26, the hub's 1.2 V.",
                      datasheet="https://www.monolithicpower.com/en/mp2152.html")


def tps53015():
    return box_symbol("TPS53015", [("5", "VIN", PI), ("4", "EN", I), ("3", "VREG5", PO), ("2", "PGOOD", OC), ("1", "VFB", I)],
                      [("10", "VBST", P), ("9", "DRVH", O), ("8", "SW", P), ("7", "DRVL", O), ("6", "PGND", P)], ref="U", width=20.32,
                      footprint="Package_SO:MSOP-10_3x3mm_P0.5mm", value_hint="TPS53015DGSR",
                      description="TI D-CAP synchronous buck controller, 4.5-28 V in, VSSOP-10 (DGS). Pin numbers from the TPS53015 datasheet pin functions table.",
                      datasheet="https://www.ti.com/lit/ds/symlink/tps53015.pdf")


def stusb4531():
    return box_symbol("STUSB4531", [("1", "VDD", PI), ("2", "CC1", B), ("3", "CC2", B), ("13", "VBUS_VS_DISCH", P), ("11", "DISCH", OC), ("9", "ADD0", I)],
                      [("10", "VBUS_EN_SNK", OC), ("4", "GPOD", OC), ("14", "HVO1", OC), ("5", "HVO2", OC), ("8", "~{ALERT}", OC), ("6", "SCL", B), ("7", "SDA", B)],
                      top=[("16", "VREG_2V7", PO), ("15", "VREG_1V2", PO)], bottom=[("12", "GND", PI), ("17", "EP", PI)], ref="U", width=30.48,
                      footprint="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.675x1.675mm", value_hint="STUSB4531QTR",
                      description="ST standalone USB-C PD sink controller, QFN-16 3x3. Pin numbers from the STUSB4531 datasheet Table 3 (pin description).",
                      datasheet="https://www.st.com/resource/en/datasheet/stusb4531.pdf")


def ncp301():
    return box_symbol("NCP301LSN20T1", [("2", "INPUT", I)], [("1", "~{RST}", OC), ("4", "NC", NC), ("5", "NC", NC)], bottom=[("3", "GND", PI)],
                      ref="U", width=15.24, footprint="Package_TO_SOT_SMD:SOT-23-5",
                      description="onsemi NCP301L 2.0 V voltage detector, open-drain active-low reset, TSOP-5. Pin numbers from the NCP300/NCP301 datasheet pin function description (TSOP-5); NVIDIA P3509 U24.",
                      datasheet="https://www.onsemi.com/pdf/datasheet/ncp300-d.pdf")


def cyusb3304():
    left = [("9", "US_RXP", I), ("8", "US_RXM", I), ("6", "US_TXP", O), ("5", "US_TXM", O), ("57", "US_DP", B), ("58", "US_DM", B), None,
            ("17", "VBUS_US", PI), ("18", "VBUS_DS", PI), None,
            ("31", "RESETN", I), ("23", "MODE_SEL0", I), ("24", "MODE_SEL1", I), ("32", "I2C_CLK", B), ("33", "I2C_DATA", B), ("20", "SUSPEND", B), None,
            ("29", "PWR_EN", O), ("30", "OVRCURR", I), None,
            ("21", "RESERVED1", B), ("22", "RESERVED2", I), ("25", "NC", NC), None,
            ("55", "XTL_IN", I), ("54", "XTL_OUT", O), None, ("2", "RREF_USB2", P), ("26", "RREF_SS", P)]
    right = [("51", "DS1_RXP", I), ("50", "DS1_RXM", I), ("47", "DS1_TXP", O), ("48", "DS1_TXM", O), ("60", "DS1_DP", B), ("59", "DS1_DM", B), None,
             ("45", "DS2_RXP", I), ("44", "DS2_RXM", I), ("41", "DS2_TXP", O), ("42", "DS2_TXM", O), ("62", "DS2_DP", B), ("63", "DS2_DM", B), None,
             ("35", "DS3_RXP", I), ("36", "DS3_RXM", I), ("38", "DS3_TXP", O), ("39", "DS3_TXM", O), ("65", "DS3_DP", B), ("64", "DS3_DM", B), None,
             ("15", "DS4_RXP", I), ("14", "DS4_RXM", I), ("11", "DS4_TXP", O), ("12", "DS4_TXM", O), ("67", "DS4_DP", B), ("68", "DS4_DM", B)]
    top = [("4", "AVDD33", PI), ("56", "AVDD33", PI), ("61", "AVDD33", PI), ("66", "AVDD33", PI), ("28", "VDD_IO", PI), None,
           ("10", "AVDD12", PI), ("16", "AVDD12", PI), ("34", "AVDD12", PI), ("46", "AVDD12", PI), ("52", "AVDD12", PI), ("53", "AVDD12", PI), None,
           ("1", "DVDD12", PI), ("3", "DVDD12", PI), ("7", "DVDD12", PI), ("13", "DVDD12", PI), ("27", "DVDD12", PI), ("37", "DVDD12", PI),
           ("43", "DVDD12", PI), ("49", "DVDD12", PI), None, ("19", "VDD_EFUSE", PI)]
    return box_symbol("CYUSB3304", left, right, top=top, bottom=[("40", "GND", PI), ("69", "EP", PI)], ref="U", width=58.42,
                      footprint="Package_DFN_QFN:QFN-68-1EP_8x8mm_P0.4mm_EP5.2x5.2mm", value_hint="CYUSB3304-68LTXI",
                      description="Infineon EZ-USB HX3 4-port USB 3.2 Gen 1 hub, 68-QFN 8x8. Pin numbers from datasheet 001-73643 Table 2 (68-QFN pin list); no pin-straps, ganged power control.",
                      datasheet="https://www.infineon.com/dgdl/Infineon-EZ-USB_HX3_USB_3.0_Hub-DataSheet-v23_00-EN.pdf")


def ap22811():
    return box_symbol("AP22811", [("5", "IN", PI), ("4", "EN", I), ("3", "FLG", OC)], [("1", "OUT", PO)], bottom=[("2", "GND", PI)], ref="U", width=15.24,
                      footprint="Package_TO_SOT_SMD:SOT-23-5", value_hint="AP22811BW5-7",
                      description="Diodes 2 A load switch with current limit and fault flag, SOT-25. Pin numbers from the AP22811 datasheet pin description (SOT-25); A: EN active high, B: EN active low. NVIDIA P3509 U21.",
                      datasheet="https://www.diodes.com/assets/Datasheets/AP22811.pdf")


def apl3552():
    return box_symbol("APL3552", [("5", "IN", PI), ("4", "EN", I), ("3", "OC*/ISET", P)], [("1", "OUT", PO)], bottom=[("2", "GND", PI)], ref="U", width=15.24,
                      footprint="Package_TO_SOT_SMD:SOT-23-5", value_hint="APL3552ABI-TRG",
                      description="Anpec 2.7-5.5 V load switch, adjustable current limit, SOT23-5. Pin numbers from the APL3552 datasheet pin description; NVIDIA P3449 U502 (the HDMI 5 V).",
                      datasheet="https://www.anpec.com.tw/ss_product_datasheet.php?psn=APL3552")


def gs7616():
    return box_symbol("GS7616SC", [("5", "IN", PI), ("6", "IN", PI), ("3", "EN", I)], [("1", "OUT", PO), ("2", "OUT", P)], bottom=[("4", "GND", PI)], ref="U", width=15.24,
                      footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6", value_hint="GS7616SC-R",
                      description="Green Solution small load switch, SOT-363. Pin order as NVIDIA P3449 U64 (gates the HDMI 3.3 V from MOD_SLEEP*); no public datasheet found, the link is the manufacturer's product list - VERIFY against the part before fab.",
                      datasheet="http://www.gstekic.com/product_list.php?product_major_id=31")


def tpd4e02b04():
    """TI TPD4E02B04DQA drawn as the flow-through part it is: USON-10 pads 1/10, 2/9, 4/7, 5/6 are the two
    ends of one channel each, 3/8 GND. KiCad's own symbol puts every pad on one side and names the second
    pads NC, which cannot carry a lane through the array; this one has one end of each channel per side."""
    name = "TPD4E02B04DQA"
    pins = []
    for i, (a, b) in enumerate((("1", "10"), ("2", "9"), ("4", "7"), ("5", "6"))):
        y = round(5.08 - i * 2.54, 4)
        pins.append(_pin(P, b, f"IO{i + 1}", -7.62, y, 0))
        pins.append(_pin(P, a, f"IO{i + 1}", 7.62, y, 180))
    pins.append(_pin(PI, "3", "GND", 0, -7.62, 90, length=3.81))
    pins.append(_pin(PI, "8", "GND", 0, -7.62, 90, length=3.81, hide=True))      # stacked on pin 3 (KLC S4.3)
    fp = "Package_SON:USON-10_2.5x1.0mm_P0.5mm"
    # 1.27 mm above IO1 and below IO4: on a connector's 2.54 mm rows the neighbouring row clears the body
    body = [Sym("symbol"), f"{name}_0_1",
            [Sym("rectangle"), [Sym("start"), -5.08, 6.35], [Sym("end"), 5.08, -3.81],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]], [Sym("fill"), [Sym("type"), Sym("background")]]]]
    unit = [Sym("symbol"), f"{name}_1_1"] + pins
    return [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 0.508]], [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            _prop("Reference", "D", (-5.08, 10.16), justify="left"), _prop("Value", name, (-5.08, 7.62), justify="left"),
            _prop("Footprint", fp, (0, 0), hide=True),
            _prop("Datasheet", "https://www.ti.com/lit/ds/symlink/tpd4e02b04.pdf", (0, 0), hide=True),
            _prop("Description", "4-channel ESD array for HDMI / USB 3, 0.5 pF, USON-10 flow-through: pads 1/10, 2/9, 4/7, 5/6 are the two ends of one channel each, 3/8 GND (TPD4E02B04 datasheet pin functions, DQA package). NVIDIA P3449 D23/D24.", (0, 0), hide=True),
            _prop("ki_keywords", KEYWORDS[name], (0, 0), hide=True),
            _prop("ki_fp_filters", fp_filter(fp), (0, 0), hide=True),
            body, unit, [Sym("embedded_fonts"), Sym("no")]]


def nmos_dual_2n7002dw():
    """Drawn as a pass element, one unit per FET: source left, drain right, gate on top, so a
    bidirectional level shifter lies in the line it shifts."""
    return units_symbol("2N7002DW", [dict(left=[("1", "S1", P)], right=[("6", "D1", P)], top=[("2", "G1", I)], width=12.7),
                                     dict(left=[("4", "S2", P)], right=[("3", "D2", P)], top=[("5", "G2", I)], width=12.7)],
                        ref="Q", footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6",
                        description="Dual N-channel MOSFET 60 V 230 mA, SOT-363, drawn as two pass elements. Pin numbers from the Diodes 2N7002DW datasheet pin configuration (Q1: S1 1, G1 2, D1 6; Q2: D2 3, S2 4, G2 5). NVIDIA P3449 Q506, the HDMI DDC shifter.",
                        datasheet="https://www.diodes.com/assets/Datasheets/ds30896.pdf")


def usb3_a_stacked():
    """Double-stacked USB 3.0 Type-A receptacle as two units, one per port, each drawn as its own
    connector facing the sheet edge: D-, D+ at the top, the SuperSpeed pairs in the middle, VBUS
    and the grounds at the bottom. Pin numbers as KiCad's Connector:USB3_A_Stacked and the Molex
    48406-0001 footprint: 1-9 one port, 10-18 the other, in USB 3.0 Std-A order, SH the shell."""
    def port(base):
        # the four SuperSpeed lines on consecutive rows, so a 4-channel flow-through ESD array sits
        # on them; two rows between them and the USB 2.0 pair, so a 2-channel array on that pair
        # clears the 4-channel one's body
        return dict(left=[(str(base + 2), "D-", B), (str(base + 3), "D+", B), None, None,
                          (str(base + 5), "SSRX-", I), (str(base + 6), "SSRX+", I),
                          (str(base + 8), "SSTX-", O), (str(base + 9), "SSTX+", O), None, None,
                          (str(base + 1), "VBUS", PI), (str(base + 4), "GND", PI), (str(base + 7), "GND_DRAIN", PI)], width=20.32)
    units = [port(0), port(9)]
    units[0]["bottom"] = [("SH", "SHIELD", P)]
    return units_symbol("USB3_A_Stacked2", units, ref="J", footprint="Connector_USB:USB3_A_Molex_48406-0001_Horizontal_Stacked",
                        description="USB 3.0 Type-A receptacle, double stacked, one unit per port. Pin numbers from the Molex 48406-0001 sales drawing (circuit 1-9 lower port, 10-18 upper port, USB 3.0 Std-A contact order) as KiCad's Connector:USB3_A_Stacked carries them; VERIFY the port-to-pin assignment against the drawing before fab.",
                        datasheet="https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/484/48406/484060001_sd.pdf",
                        value_hint="USB-A PORT1")


LIBRARIES = {
    "calico-ic": [k64, usb2517, tps2553, pca9517a, tps54560,
                  efm8, gs7116, mp2152, tps53015, stusb4531, ncp301, cyusb3304, ap22811, apl3552, gs7616, tpd4e02b04, nmos_dual_2n7002dw],
    "calico-electromechanical": [usb_a_stacked, jw1fsn, jetson_nano_sodimm, usb3_a_stacked],
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
