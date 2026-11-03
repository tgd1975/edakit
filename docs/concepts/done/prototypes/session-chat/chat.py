"""The prototype of a ```chat fence turned into HTML – what docs/pages.py would do on assembly (session-chat.md, S.2).

    python3 chat.py session.md out/session.html     a standalone page with chat.css inlined, for the screenshots

The format, one entry a line, an indented line continuing the one above:

    --- <step>             a step of the steps pages, as a divider
    you: <text>            what the person types
    claude: <text>         what Claude says
    ran: <text>            what Claude ran – a quiet line, no bubble
    do: <text>             what the person does outside the chat: an install, a click, a new session, paying
      † <text>             under a do: its footnote – for a click in EasyEDA: KiCad needs none, and the issue upstream
    img: <path> | <alt>    a picture Claude shows
    form: <title>          Claude Code's question form, then per question:
      ? <question>
      - <option>           the recommended one first, marked "(recommended)"
      > <answer>           what the person picked or typed

The tally under the chat is counted from the entries, so it cannot drift from them – under a whole session only, one
that starts with step 1; an excerpt has none.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^```chat\n(.*?)^```\n", re.M | re.S)
HERE = Path(__file__).resolve().parent


def parse(text):
    """[(kind, value)] – value a string, or for a form {title, questions: [{q, options, answer}]}."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and entries:
            kind, value = entries[-1]
            body = line.strip()
            if kind == "form" and body[:2] in ("? ", "- ", "> "):
                mark, rest = body[0], body[2:]
                if mark == "?":
                    value["questions"].append({"q": rest, "options": [], "answer": ""})
                elif mark == "-":
                    value["questions"][-1]["options"].append(rest)
                else:
                    value["questions"][-1]["answer"] = rest
            elif body.startswith("† ") and kind in ("do", "note"):
                entries.append(("note", body[2:]))
            elif kind != "form":
                entries[-1] = (kind, f"{value} {body}")
            continue
        if line.startswith("--- "):
            entries.append(("step", line[4:].strip()))
            continue
        kind, sep, rest = line.partition(": ")
        if not sep or kind not in ("you", "claude", "ran", "do", "img", "form"):
            raise SystemExit(f"chat: not an entry: {line!r}")
        entries.append((kind, {"title": rest, "questions": []} if kind == "form" else rest))
    return entries


def tally(entries):
    you = sum(k == "you" for k, _ in entries)
    forms = [v for k, v in entries if k == "form"]
    answers = sum(len(f["questions"]) for f in forms)
    do = sum(k == "do" for k, _ in entries)
    return {"typed": you, "forms": len(forms), "answers": answers, "outside": do}


LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def code(text):
    """`/edakit:…`, `edakit …` and paths set in mono, [text](url) a link, the rest escaped."""
    out, last = [], 0
    for m in LINK.finditer(text):
        out.append(mono(text[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2))}">{mono(m.group(1))}</a>')
        last = m.end()
    return "".join(out) + mono(text[last:])


def mono(text):
    """The commands – on the site the list of edakit's own –, the slash commands and the paths in mono."""
    out = html.escape(text)
    return re.sub(r"(/edakit:[\w-]+|edakit (?:block|part|check|sim|stock|cost|order|schematic|gate|req|graph|explain|cart|pcb|route|release)\b[\w -]*?(?= ·|:|$|\.)|[\w./-]+\.(?:toml|json|md))",
                  r"<code>\1</code>", out)


def render(entries):
    parts = ['<div class="chat">']
    for n, (kind, value) in enumerate(entries):
        if kind == "note":
            continue                     # written inside the do above it
        if kind == "step":
            parts.append(f'<div class="chat-step"><span>{html.escape(value)}</span></div>')
        elif kind in ("you", "claude"):
            who = "You" if kind == "you" else "Claude"
            parts.append(f'<div class="chat-msg chat-{kind}"><span class="chat-who">{who}</span>'
                         f'<p>{code(value)}</p></div>')
        elif kind == "ran":
            parts.append(f'<div class="chat-ran"><span>ran</span> {code(value)}</div>')
        elif kind == "do":
            notes = []
            for k, v in entries[n + 1:]:
                if k != "note":
                    break
                notes.append(f'<p class="chat-note">† {code(v)}</p>')
            mark = " †" if notes else ""
            parts.append(f'<div class="chat-do"><span class="chat-do-label">You, outside the chat</span>'
                         f'<p>{code(value)}{mark}</p>{"".join(notes)}</div>')
        elif kind == "img":
            path, _, alt = (s.strip() for s in value.partition("|"))
            parts.append(f'<figure class="chat-img"><img src="{html.escape(path)}" alt="{html.escape(alt)}">'
                         f'<figcaption>{html.escape(alt)}</figcaption></figure>')
        elif kind == "form":
            rows = []
            for q in value["questions"]:
                opts = "".join(f'<li{" class=\"chat-rec\"" if i == 0 else ""}>{code(o)}</li>'
                               for i, o in enumerate(q["options"]))
                row = "chat-q" if opts else "chat-q chat-q-row"
                rows.append(f'<div class="{row}"><p>{code(q["q"])}</p>'
                            + (f"<ol>{opts}</ol>" if opts else "")
                            + f'<p class="chat-a">{code(q["answer"])}</p></div>')
            parts.append(f'<div class="chat-form"><div class="chat-form-title">{html.escape(value["title"])}'
                         f'<span>{len(value["questions"])} '
                         f'question{"s" if len(value["questions"]) != 1 else ""}</span></div>{"".join(rows)}</div>')
    whole = bool(entries) and entries[0][0] == "step" and entries[0][1].startswith("1 ")
    t = tally(entries)
    parts.append("</div>") if not whole else parts.append(f'<div class="chat-tally"><b>Your part:</b> {t["typed"]} messages typed, {t["answers"]} answers '
                 f'in {t["forms"]} forms, {t["outside"]} things done outside the chat.</div></div>')
    return "\n".join(parts)


def page(markdown):
    m = FENCE.search(markdown)
    body = render(parse(m.group(1)))
    css = (HERE / "chat.css").read_text()
    head = markdown[:m.start()]
    title = re.search(r"^# (.+)$", head, re.M).group(1)
    intro = "".join(f"<p>{html.escape(re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', p.strip()))}</p>"
                    for p in head.split("\n\n")[1:] if p.strip())
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{css}</style></head><body><main class="md-typeset"><h1>{html.escape(title)}</h1>{intro}'
            f'{body}</main></body></html>\n')


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out = page(src.read_text())
    # the pictures relative to the output page, as the site would copy them under files/
    up = "../" * (len(dst.parent.relative_to(src.parent).parts) + 5)
    out = out.replace('src="../../../../../', f'src="{up}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out)
    print(dst, tally(parse(FENCE.search(src.read_text()).group(1))))
