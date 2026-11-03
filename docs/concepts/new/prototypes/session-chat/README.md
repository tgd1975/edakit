# Prototype: a session as a chat

The sketch of [session-chat.md](../../session-chat.md), not on the site's navigation and not built into
`docs/pages.py`.

- `session.md` – the page as it would stand in `docs/`: an intro of two paragraphs and one ```` ```chat ```` fence, the
  walkthrough's board from the first sentence to the cart. On GitHub the fence reads as a plain transcript.
- `chat.py` – the fence turned into HTML, as `docs/pages.py` would do it on assembly; the tally under the chat counted
  from the entries. `python3 chat.py session.md out/session.html` writes a standalone page.
- `chat.css` – the chat's styles in the tokens of `docs/brand/tokens.json`, for `docs/brand/edakit.css`.
- `out/session.html` – the rendered page; `out/session-light.png` its top at 900 px, light, up to step 6;
  `out/session-dark-phone.png` steps 8 and 9 at 390 px, dark.

Its tally, counted by `chat.py`: 8 messages typed, 15 answers in 5 forms, 7 things done outside the chat.
