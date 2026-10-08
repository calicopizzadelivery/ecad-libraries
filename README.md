# ecad-libraries

The house KiCad libraries: symbols KiCad's standard libraries lack, built
from datasheet pin tables, plus a footprint library for the day a footprint
has to be made rather than taken from KiCad. Used from projects as a git
submodule, so every project is pinned to a known revision of these files.

```
symbols/
  calico-ic.kicad_sym                 ICs
  calico-electromechanical.kicad_sym  connectors, relays, switches
footprints/
  calico.pretty/                      house footprints
tables/
  sym-lib-table, fp-lib-table         fragments to copy into a project
tools/
  build_symbols.py                    the source of truth for symbols/
  build_footprints.py                 the source of truth for footprints/
  glyphs.py, kisym.py                 text widths and the s-expression writer
```

## Using it in a project

```bash
git submodule add https://github.com/calicopizzadelivery/ecad-libraries hardware/kicad/libs
git clone --recurse-submodules <project>      # for anyone cloning the project later
```

Copy `tables/sym-lib-table` and `tables/fp-lib-table` into the KiCad project
directory (next to the `.kicad_pro`); they refer to the libraries as
`${KIPRJMOD}/../libs/...`, which is right when the project lives in
`hardware/kicad/<board>/` and the submodule in `hardware/kicad/libs/`. Nothing
goes into KiCad's global library tables: those are per user and do not travel
with the project.

Symbols are referenced as `calico-ic:USB2517` and so on. To take a newer
library revision, update the submodule deliberately (`git submodule update
--remote`, commit the new pointer), then run *Update Symbols from Library* in
KiCad, or regenerate if the project is generated. Releases are tagged
`vX.Y.Z` and listed in [CHANGELOG.md](CHANGELOG.md).

## How symbols are made

`tools/build_symbols.py` builds every symbol from a pin table transcribed
from the part's datasheet; each symbol's Description says which table. The
builder enforces the house rules from
[ecad-standards](https://github.com/calicopizzadelivery/ecad-standards):

- pin names never overlap: rows are kept clear above the first side pin and
  below the last for the vertical names of top and bottom pins, and the body
  is wide enough for the longest left and right names plus a gap;
- reference and value sit above the body, side by side when they fit and
  stacked when they do not, or below it when the top edge carries pins;
- supply pins along the top edge, ground pins along the bottom, so the
  hub-and-fan-out layout can bus them;
- and the KiCad Library Conventions where they do not conflict: every pin on
  the 100 mil grid of the origin, 2.54 mm pins, 20 mil pin-name offset,
  keywords, a footprint filter that matches the default footprint, a real
  datasheet link.

The generated files are committed. `tools/build_symbols.py --check` fails
when they differ from what the builder produces, and the CI runs it on every
push, so a symbol is changed by editing the pin table, never the output.

To add a part: transcribe its pin table into a builder function, cite the
table in the description, add a keywords entry, run the builder, run the KLC
checker (below), add a changelog line, tag.

## KLC check

```bash
git clone --depth 1 https://gitlab.com/kicad/libraries/kicad-library-utils.git /tmp/klu
python3 /tmp/klu/klc-check/check_symbol.py -v symbols/*.kicad_sym
```

The CI runs this as a report, not a gate, because four of its findings are
house decisions:

- *Symbol not centred on origin* (S3.1): the rows kept clear for vertical
  pin names make the body taller above the side pins than below.
- *Power pins should be on the left / right* (S4.2): supply pins go along the
  top edge and ground pins along the bottom, by house style.
- *Ground pins at the bottom* on connectors (S4.2): a connector's pins all
  face the sheet edge, in the connector's own order.
- *Pins 3, 5, 7 missing* and *NC pin type* on JW1FSN (S4.5, S4.6): the
  footprint has pads 1, 2, 4, 6 and 8 only, and "NC" is the normally-closed
  contact, not a no-connect.
- *Power output pins at the right* (S4.2) on TPS53015 and USB2517: a
  regulator's internal-supply output (VREG5, VDD18) sits where its capacitor
  is drawn, beside the input pins.

Everything else it reports is a defect to fix.

## Footprints and 3D models

Take footprints from KiCad's own libraries while they fit the part. A
footprint that has to be made is built by `tools/build_footprints.py` from
the manufacturer's drawing, which its description cites with the dimensions
taken from it, and goes into `footprints/calico.pretty`; `--check` and the CI
keep hand edits out, as for symbols. A KiCad footprint that needs one change
(a pad trimmed for a fab's minimum) is rebuilt here pad for pad from KiCad's
numbers with the change named in its description and `_<Change>` on its
name, and keeps the KiCad part's 3D model (`FP(..., model=...)`). `check_footprint.py` runs as a report:
the anchor of a connector sits on its mechanical datum rather than the pad
centre (F6.2), and 3D models (F9.3) are referenced as
`${KIPRJMOD}/../libs/3dmodels/calico.3dshapes/<footprint>.step` but none
exist yet. Models belong in `3dmodels/calico.3dshapes/` on Git LFS (see
`.gitattributes`).

## Licence

Apache-2.0, see [LICENSE](LICENSE). Symbols are drawn from publicly
available datasheets; the datasheets themselves are not included.
