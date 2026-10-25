"""edakit – from a JSON hardware graph to a manufactured PCB with EasyEDA Pro.

The graph is the single source of truth. edakit checks it, simulates it, generates the schematic and the PCB in
EasyEDA Pro through the easyeda-mcp-pro bridge, routes with Freerouting and releases the manufacturing data only
after every stage of the release gate has passed. See handbook/README.md.
"""

__version__ = "0.1.0"
