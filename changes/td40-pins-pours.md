patch
- EasyEDA's pours follow the outline and keep every mounting and tooling hole free with a NO_POURS region instead of a notch to the edge, and the tooling holes stay on the board while the pours fill (E-13) – the copper of a board changes at its next `route all|pours`, so its layout sign-off M-5 is asked for again.
- `part build` modifies the pins of a symbol box in place instead of deleting and creating them (E-11); the orphan-attribute sweep of `schematic layout` stays as a cheap check (E-10).
