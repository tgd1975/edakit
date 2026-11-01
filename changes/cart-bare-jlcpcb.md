patch
- edakit cart: a bare board at JLCPCB passes ORDER.form and ORDER.files – its quote page has no "Product Description" (now a checkout field without assembly, profile `fields.<key>.assembly`) and names no upload (`unshown_bare`: the cart line names the Gerber); "PCB Assembly" and "Stencil" are in the profile's ignore, and the job says "bare" instead of "5 assembled" (live run 2026-11-01).
