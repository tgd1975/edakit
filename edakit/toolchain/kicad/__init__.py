"""KiCad as edakit's tool chain (toolchain = "kicad", handbook 16): the files of one KiCad project per board, written
by edakit from its own data, and kicad-cli for ERC, DRC with the zone fill, netlist, BOM and the manufacturing files.

    sexp.py       S-expressions: read and write KiCad's file format
    library.py    the board's library: footprints (.kicad_mod) and symbols (.kicad_sym) from the parts database
    board.py      the PCB (.kicad_pcb) and its rules (.kicad_pro, .kicad_dru): written from the plan and the routing,
                  read back into the files the shared checks read (board.json, pcb.json, geometry.json)
    schematic.py  the schematic (.kicad_sch) from schematic_layout.Layout
    cli.py        kicad-cli

Units at the boundary: edakit's mil with y up (EasyEDA's frame) on the inside; KiCad's mm with y down in the files.
A point (x, y) in edakit's frame lies at (x mm, -y mm) in KiCad – so the Gerber files of both tool chains share their
coordinates.
"""
