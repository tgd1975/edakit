patch
- `[silk] designators = "none"` leaves a board without designators: `silk apply` hides both sides and places none,
  GEO.silk asks no part for one and warns on a part that shows one; any other value than `top`, `bottom` or `none` is a
  board-file error (#396).
