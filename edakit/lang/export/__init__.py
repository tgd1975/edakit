"""The exports of the circuit language (T.20 to T.23, language 9 and 10): a project as SysML v2 and as KerML, textual
and as the JSON serialization of KerML clause 10.4 – one mapping, an element tree, applied twice.

    model.py   the element tree of a project: build(cfg) from the resolved graph and the source set
    sysml.py   the tree in SysML v2's textual notation
    kerml.py   the tree in KerML's textual notation; Electrical.kerml from the library
    json.py    the tree as an array of element objects with @id and @type
"""
