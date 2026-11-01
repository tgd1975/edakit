# Getting edakit known: for whom, where it is shown, what it costs the owner

Status 2026-11-01: decided – the owner took the three decisions the same day in a decision round in Claude Code's
form, each as recommended, and confirmed what Claude decided itself (the table at the end); a fifth the same evening,
the plugin's text, and on the owner's word K.2, K.3 and K.9 as one branch and one pull request. K.1 built the same
day on the owner's word: the repository's description, topics and homepage set with `gh api`, the social preview made
(`outreach/social-preview.png`) and uploaded by the owner. Each further step starts on the owner's word, listed in
`TODO.md`. Written against main at `bef46c2`, checked against `4e7064a` (claude-independence.md decided meanwhile: one
more occasion under K.8). Asked for by the owner: a concept for how edakit gets out to people – where to post, where to
register and list it, for makers, users and developers alike –, at low effort, since the owner has put enough time
into the project, and yet effective, since others should use edakit. Builds on [documentation.md](documentation.md)
(the entry layer D.2, the "is it for me" numbers D.7, the gallery D.9) and [versioning.md](versioning.md) (1.0.0 once
D.2 is built, V.6). The rules of the channels named here were read on 2026-11-01 from their own pages (Sources).

## The short answer

edakit is launched once, as 1.0.0, in one week, and after that only when there is something to show. Until then
nothing is posted: a reader who arrives at today's README – 260 lines, a patched bridge extension in the setup – does
not come back, and a launch cannot be repeated.

- **When:** after the start page and the quickstart (D.2) and the bell's page in the gallery (D.9). That is also when
  1.0.0 is set (V.6). Best with the bell built and ringing on video, in the first half of December – a Christmas build
  in December is its own story.
- **Where:** where the two groups already are that need nothing new to try edakit. The first group has Claude Code:
  Anthropic's plugin directory, awesome-claude-code and r/ClaudeAI. The second group orders boards at JLCPCB with
  EasyEDA or KiCad: Hackaday, the Adafruit blog, the KiCad forum and OSHWLab. On top of that, one Show HN. The
  repository's description and topics and the directory listing keep working without anyone posting.
- **How:** Claude prepares everything – the facts, the drafts, the pictures – in
  `docs/concepts/new/outreach/`. The owner sends it from their own accounts. Hacker News and awesome-claude-code allow
  only text a person wrote and posted, so there the owner writes; the other places get Claude's drafts, read by the
  owner.
- **Afterwards:** nothing on a schedule. Every later post has an occasion: a project in the gallery, posted where its
  own crowd is (the pedal among pedal builders), or a release that changes how a project works.
- **The owner's time:** about an hour before the launch, one afternoon for the Show HN, ten minutes per other place;
  after that, while interest lasts, about half an hour a week for issues, which Claude sorts and answers in draft.
- **Not:** a Discord, a newsletter, a blog site, regular social media, Product Hunt, paid ads, a PyPI release, talks.

Everything this leaves behind is text in the repository – the kit, the numbers, what each place brought. Only the
accounts and the posts themselves are outside, and they are the owner's.

## What there is to show

**The sentence.** Circuit design as code: you describe the circuit as text, and Claude Code does the rest – checks,
simulation, schematic, PCB, routing –, and nothing goes to the maker that the release gate has not checked on the
exported files.

**What sets it apart in 2026.** What is out there are MCP servers that give a model access to KiCad or EasyEDA – KiCad
MCP Pro, Konnect, easyeda-mcp-pro, which edakit itself uses. They let a model draw. edakit adds what makes a board
something to trust:

- the design as text in git, every decision with it;
- 118 codes in 9 domains, each seen red once in a test;
- ngspice over every supply, load and tolerance corner;
- reviewer agents independent of the designing session;
- a gate on the files that go to the maker.

The posts lead with that, not with "AI designs your PCB". The electronics crowd asks first whether the result is
garbage. The answer is the gate and the released boards. Its second question is the cost – the numbers from the evals
(D.7).

**The evidence:**

- the bell – five boards released, the variants side by side;
- the two walkthroughs – a coin cell on EasyEDA, a 555 on KiCad;
- `edakit check` under a second, `edakit sim` with 1112 checks on the bell;
- "try it in two minutes", `uvx … edakit check` on the example, without EasyEDA.

A board in hand beats every render: a photo of the built bell and ten seconds of it ringing are what Hackaday needs as
its header picture.

**The limits, said in every post:**

- tested on Linux;
- EasyEDA Pro as a desktop program with a patched bridge, KiCad 10 without one;
- two copper layers, DC operating points and a few transient runs;
- easyeda-mcp-pro is licensed PolyForm Noncommercial, so a company comes through the KiCad tool chain;
- the regulatory review is support, not legal advice.

The communities punish hype about AI and respect a limit said first.

**The name.** To data people, "EDA" means exploratory data analysis. On PyPI, `edakit` is a data-analysis toolkit of
2022 (0.0.1). So every post says "edakit (PCB, EasyEDA, KiCad)", and the repository's description and topics carry the
words people search for. A PyPI release is not needed – the plugin and `uvx --from git+…` cover it –, and a claim for
the name (PEP 541) is not worth the effort.

## For whom

| Group | Why they come | Where they are | What they need first |
| --- | --- | --- | --- |
| Claude Code users who make hardware now and then | They have the hardest part, Claude Code, already | `/plugin`, the plugin directory, awesome-claude-code, r/ClaudeAI | the plugin listed, "try it in two minutes" |
| Makers who order at JLCPCB with EasyEDA or KiCad | Fewer mistakes, less to know, the order up to the cart | Hackaday, the Adafruit blog, OSHWLab, the KiCad forum, Reddit | a real board, the gate's findings on it, the limits |
| Developers who would add rules or blocks | They come through the first two groups | GitHub | the developer page (D.6), the proposals (handbook 14.4) |

Companies are not a target: the noncommercial licence of the EasyEDA server and "tested on one machine" speak against
them, and a company comes through KiCad if at all. No post is aimed at them.

## What must be true before the launch

A visitor arrives once. What they find decides, so these are the launch's conditions:

1. **The entry (D.2):** the start page on one screen, the case, "try it in two minutes", the quickstart without
   EasyEDA. The offline way first is the answer to the hardest hurdle, the EasyEDA setup.
2. **Boards to look at (D.9):** the bell's page with its schematic, its board and its variants, from its release.
   Ideally with a photo of the built board.
3. **The cost (D.7):** what a check, a decision round, a circuit design costs in tokens. Hacker News asks within the
   first hour.
4. **Ready for the plugin directory (K.2):** the directory's security scan looks for "behavior that a plugin doesn't
   disclose" and asks that the README "describe … everything the plugin runs, sends, or fetches". edakit does several
   things that must be disclosed:
   - it downloads Freerouting;
   - it installs easyeda-mcp-pro (pinned);
   - it queries JLCPCB's catalogue and fetches datasheets;
   - it publishes releases with `gh`;
   - the skill cart fills the makers' forms with Claude in Chrome;
   - the skill new-project writes Claude Code settings into a project, after the user's OK;
   - it runs two hooks.

   One section in the README says it all. `plugin.json` gets its `version` and the description without "JSON hardware
   graph" (documentation.md, finding 7 – the owner's text).

   What the directory checks and edakit meets today:
   - a README of at least 40 words and a licence (MIT);
   - launchers pinned (`easyeda-mcp-pro@1.6.0`, `uv run` in the plugin);
   - 3.3 MiB as an archive, under the 50 MiB limit;
   - no credentials in the files.

   Held for a person to review, not refused: 974 files where "512 files or fewer" is asked, and two files over 256 KiB
   (`docs/catalog/index.html`, `uv.lock`).
5. **Issues that can be answered (K.3):** an issue form for bugs, with `edakit --version`, `edakit doctor`, the system
   and the tool chain; one for questions; one for "built with edakit", which a project's page in the gallery comes
   from. One line on the start page says how issues are answered: by one person with Claude, as time allows.

The repository's front (K.1) and the directory listing (K.4) can come before, as soon as their conditions hold: they
bring readers slowly and need no launch.

## Where – the places, in order of what they bring for their effort

### At the launch

| # | Place | Audience | What goes there | Rules that bind | Owner's time |
| --- | --- | --- | --- | --- | --- |
| 1 | **Anthropic's plugin directory** – the community marketplace `claude-community` and the catalog on claude.ai | Claude Code users looking for a plugin | the repository at a tag; the listing from `plugin.json` and the README; a contact email; answers on data handling (Claude drafts them) | "Anyone on a paid Claude plan can submit"; a first submission that fails the security scan is rejected; a person reviews a new listing; "Review time isn't fixed" | 15 min, once – new versions follow by webhook |
| 2 | **Show HN** | developers, makers among them; the largest reach, the most variance | a post that people can try – `uvx … edakit check` on the example, no account, no signup | "Please don't put generated text in HN posts. Write your text yourself"; comments: "Don't post generated text or AI-edited text"; no asking for votes | 20 min for the post, an afternoon and evening of answers |
| 3 | **Hackaday**, the tip form | makers, the largest hardware audience | the bell: header photo, what, why, how, the link to its page | a strong header picture; what, why, how | 10 min |
| 4 | **The Adafruit blog**, contact form, category "Cool thing for the Adafruit Blog!" | makers; it featured AI tools for KiCad in April and October 2026 | title, link, a short description | no negative content | 5 min |
| 5 | **awesome-claude-code** | Claude Code users | one line, a description and no pitch, no emoji | only through the web form, "created by human beings", not with `gh`; the repository at least 14 days old with active development – from 2026-11-08 | 5 min |
| 6 | **r/ClaudeAI** | Claude Code users | a showcase post | Rule 7 (showcase); posts in the feed need 50 karma, otherwise the showcase megathread | 15 min, an hour of answers |
| 7 | **The KiCad forum** (forum.kicad.info, Software) | KiCad users; MCP servers for KiCad were presented there | the KiCad tool chain with the 555 walkthrough, its limit said: no real project on KiCad yet | the forum's rules | 10 min |
| 8 | **OSHWLab** (EasyEDA's project site) | EasyEDA users browsing open projects | the bell's EasyEDA project made public, "generated with edakit", the link | the bell's session does it, on the owner's word; OSHWLab Stars, running to 2026-12-31, can pay boards of open projects – a bonus, not the goal | 15 min |

### Now and then – at most two, with a real board

r/electronics, r/arduino (the bell as a build, edakit in one line), the EEVblog forum, mikrocontroller.net (German,
Projekte & Code), a line in the README of easyeda-mcp-pro that edakit builds on it (a pull request upstream, on the
owner's word). These crowds are the most sceptical of AI. A post there leads with the board and the gate, or is not
made.

### Not

| What | Why not |
| --- | --- |
| Product Hunt | a launch day of its own, an audience with little hardware |
| X, Bluesky, Mastodon, LinkedIn as a campaign | needs a rhythm; one post on the launch day only where the owner has an account in use anyway |
| A Discord, a forum, a newsletter of edakit's own | one more place to watch; the issues are the one place |
| GitHub Discussions | the same – one place |
| A blog or a page of its own beyond the site | the site is the page; the gallery is the article |
| Hackaday.io as a project page | one more page to keep current; the gallery page does it |
| PyPI | the name is taken, and the plugin and `uvx` cover it |
| MCP registries | edakit is not an MCP server |
| Talks (FOSDEM's Open Hardware devroom, 39C3 in Hamburg) | weeks of preparation – a lightning talk only if the owner goes anyway |
| Paid ads | money for a hobby tool with no budget to win back |

## What spreads by itself afterwards

- **Projects in their own communities.** A maker who builds something shows the thing, not the tool – and that is
  welcome everywhere a tool post is not. The bell among Arduino builders, the pedal among pedal builders, the steering
  wheel among sim racers: each project in the gallery is posted once where its own crowd is, with edakit as the
  last line. This is the recurring channel, and it costs only the occasion.
- **The gallery takes others' projects.** "Built something with edakit? Open an issue with the link" (K.3) – Claude
  writes the page from the project's release, in D.9's form. The users become the content.
- **The release names its tool.** `edakit release publish` writes one line into the project's GitHub release:
  "Released with edakit 1.2.0", with the link. That is provenance – which version checked the files – and every
  project's release page links back. On by default, one key turns it off (decision 3).
- **The first 48 hours count more than the post.** An answer within hours makes the thread; the same answer two days
  later is read by nobody. That is why the launch week spreads the places over several days.

## Who does what

| | Claude | The owner |
| --- | --- | --- |
| Before | the repository's front (K.1); the README section and `plugin.json` (K.2); the issue forms (K.3); the kit (K.5): the fact sheet with fresh numbers, the drafts, the pictures, the data-handling answers | the social preview image uploaded (Settings, 1 min – GitHub has no API for it); the directory submission (K.4, the acknowledgements are the owner's); the drafts read; the bell's photo and video, if built |
| Launch week | the day's facts ready; the referrers and stars noted per day | the posts sent; Show HN written in their own words; the answers on the day |
| After | issues sorted, answers drafted, a project's page from its release, the numbers per place after two weeks (K.7) | answers sent; the next occasion named |

Claude never posts in the owner's name on its own: every post is outward-facing and needs the owner's word, and Hacker
News and awesome-claude-code allow only the owner's own hand. Forms without such a rule – Hackaday, Adafruit, the
directory up to its acknowledgements – Claude can fill with Claude in Chrome on the owner's word, the owner sending
them.

## Measures – done when

- **The baseline, 2026-11-01:** 0 stars, 0 forks, 81 views from 1 visitor (the owner), no referrer but github.com.
- **What each place brought:** GitHub keeps the traffic for 14 days only. So Claude reads
  `gh api repos/tgd1975/edakit/traffic/popular/referrers` and `…/traffic/views` daily in the launch week and once two
  weeks later, and writes a table per place – visitors, stars before and after – into this concept. The next occasions
  go only where something came of it.
- **Three months after the launch:**
  - 100 stars;
  - three people outside who ran `edakit check` and said so in an issue;
  - one project by someone else in the gallery;
  - the owner's time on all of this under ten hours.

  These are the measure, not a forecast. If they are missed, the places that brought nothing are dropped, not
  tried harder.

## Risks – what we can influence

- **Newcomers fail at the EasyEDA setup.**
  - *Probability:* likely, for most who go on to the board.
  - *Cost:* a lost user each, a few issues.
  - *Held by:* the offline way first – try it in two minutes, the quickstart without EasyEDA –, KiCad as the way
    without a bridge, and `edakit doctor` in the bug form.
- **AI scepticism in electronics forums.**
  - *Probability:* likely on Reddit and in the forums, occasional on Hacker News.
  - *Cost:* an evening of answers, a few downvotes.
  - *Held by:* posts that lead with the gate and a real board, the limits first, no "AI designs your PCB"; the most
    hostile places left out.
- **Support load after a front page.**
  - *Probability:* occasional.
  - *Cost:* 10 to 30 issues in a week, one to three hours a week for a few weeks.
  - *Held by:* Claude sorting them and drafting the answers, the forms, the line on how issues are answered.

  The proposals pipeline is not touched: it runs only on the owner's sealed issues, so a stranger's issue costs no
  credentials (CLAUDE.md).
- **The directory's security scan refuses the first submission.**
  - *Probability:* possible – the hooks, the settings written by new-project, the downloads.
  - *Cost:* a fix round and a wait.
  - *Held by:* the README section of K.2 before submitting.
- **The launch waits too long for D.2.**
  - *Probability:* possible – D.2 to D.7 wait for the other todos.
  - *Cost:* nothing lost, only time.
  - *Held by:* K.1 and K.4 going ahead; the rest waits, and nothing is posted half-ready.
- **Questions about the licence of easyeda-mcp-pro.**
  - *Probability:* occasional, from companies.
  - *Cost:* one answer.
  - *Held by:* the limit said in every post, the README's licence line.

## Steps

| Step | What | Who | Size | Waits for |
| --- | --- | --- | --- | --- |
| K.1 | The repository's front: description, topics (`easyeda`, `kicad`, `pcb`, `pcb-design`, `jlcpcb`, `electronics`, `hardware-as-code`, `claude-code`, `claude-code-plugin`, `ngspice`, `freerouting`), the site as homepage – with `gh api`; the social preview (1280 × 640) from the brand and the bell's board, uploaded by the owner. Done 2026-11-01: [outreach/social-preview.png](outreach/social-preview.png), the bell's board from its release of 2026-11-01 | Claude, the owner's click | S | – |
| K.2 | Ready for the directory: the README section on what edakit runs, sends and fetches; `plugin.json` with `version`, and the texts of decision 5 in `plugin.json` and `marketplace.json` | Claude, a branch, a patch | S | – (or with D.2) |
| K.3 | The issue forms: bug, question, "built with edakit"; the line on how issues are answered | Claude, a branch | S | – |
| K.4 | The directory submission at claude.ai/directory/manage: the repository at its tag, the data-handling answers from the kit, new versions by webhook | the owner | 15 min | K.2 |
| K.5 | The kit in `docs/concepts/new/outreach/`: the fact sheet (numbers from a fresh run, links, limits, the expected questions with the facts for each answer), the texts for Hackaday, Adafruit, r/ClaudeAI, the KiCad forum, OSHWLab, the line for awesome-claude-code, the pictures; notes for the Show HN, not its text | Claude | M | D.2, D.7, D.9 |
| K.6 | The launch week: Monday 1.0.0 (V.6); Tuesday Show HN, on a weekday afternoon in Germany, morning on the US east coast; Wednesday r/ClaudeAI; Thursday Hackaday and Adafruit; the week after the KiCad forum and OSHWLab; awesome-claude-code in the same week (possible from 2026-11-08) | the owner | an afternoon, then 15 min a day | K.1 to K.5 |
| K.7 | Two weeks later: the referrers read, the table per place into this concept, what worked named | Claude | S | K.6 |
| K.8 | Then, per occasion: a project in the gallery posted where its crowd is; a release that changes how a project works, posted where K.7 found readers – among them another assistant supported ([claude-independence.md](claude-independence.md)), which opens the places of its users; no schedule | the owner, Claude's draft | S each | – |
| K.9 | "Released with edakit" in the GitHub release of `edakit release publish`, with a key to turn it off | Claude, a branch, a patch | S | decision 3 |

K.2, K.3 and K.9 go as one branch, `outreach-k2-k3-k9`, a commit per step, one fragment and one pull request – one
version, one OK, on the owner's word of 2026-11-01: they belong together, K.2 and K.3 both change the README, and three
pull requests would be three runs of the checks and three versions for one subject.

The kit is a source, like the rest of this folder, and lands through the notes lane; the site shows it before it is
posted, which does no harm.

## Decisions

Taken by the owner on 2026-11-01, in a decision round in Claude Code's form; "accepted" is the owner's yes to the
recommendation.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | When to launch | after D.2, D.7 and D.9, with the bell built – photo and video –, aimed at the first half of December | after D.2 alone, the release pictures instead of a photo; now, with today's README | accepted |
| 2 | Which places in the owner's own name | Show HN and r/ClaudeAI, besides the forms | the forms and r/ClaudeAI, no Show HN; the forms only (directory, awesome-claude-code, Hackaday, Adafruit) – no writing of the owner's own, much less reach; all of them and the electronics forums | accepted |
| 3 | "Released with edakit" in a project's GitHub release | on by default, one key turns it off | a snippet in the documentation that a project may copy; nothing | accepted |
| 4 | What Claude decided itself | K.1 now; issues only, no Discussions; the directory with new versions by webhook; OSHWLab through the bell's session, on the owner's word; the "Not" list; the kit in `outreach/`; the measures | K.1 at the launch only | confirmed |
| 5 | The plugin's text – `displayName` and `description` in `.claude-plugin/plugin.json`, the two descriptions in `.claude-plugin/marketplace.json`: the first text in `/plugin` and the directory, today "From a JSON hardware graph … with EasyEDA Pro" (documentation.md, finding 7) | the repository's description of K.1, one wording everywhere: displayName "edakit – circuit design as code"; description "Circuit design as code: the circuit as text in your repository, checked by rules and an ngspice simulation, drawn as schematic and PCB in EasyEDA Pro or KiCad, routed with Freerouting and released through a gate on the manufacturing files – skills, agents and the edakit command line."; marketplace.json "edakit: circuit design as code for Claude Code – checks, simulation, schematic, PCB, release gate." and "Skills, agents, the EasyEDA MCP server and the edakit command line – EasyEDA Pro or KiCad." | short: "Circuit design as code with Claude Code: checks, simulation, schematic, PCB and a release gate – EasyEDA Pro or KiCad."; corrected only: TOML for JSON, KiCad added | accepted |

## Sources

- Anthropic, the plugin directory: [publish](https://claude.com/docs/directory/publish),
  [pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist.md),
  [submission status](https://claude.com/docs/directory/submission-status.md),
  [Anthropic's marketplaces](https://code.claude.com/docs/en/plugins/anthropic-marketplaces),
  [claude-plugins-community](https://github.com/anthropics/claude-plugins-community) – read 2026-11-01.
- [awesome-claude-code, CONTRIBUTING.md](https://github.com/hesreallyhim/awesome-claude-code/blob/main/CONTRIBUTING.md).
- Hacker News: [Show HN](https://news.ycombinator.com/showhn.html),
  [guidelines](https://news.ycombinator.com/newsguidelines.html) – the rule on generated text since March 2026.
- [Hackaday, submit a tip](https://hackaday.com/submit-a-tip/),
  [how best to get your project on Hackaday](https://hackaday.com/2021/04/27/how-best-to-get-your-project-on-hackaday).
- [Adafruit, how to send a blog tip](https://learn.adafruit.com/how-to-send-a-blogtip-to-adafruit); its posts on
  AI-assisted PCB design of [2026-04-22](https://blog.adafruit.com/2026/04/22/kicad-mcp-pro-server-connects-kicad-to-your-ai/)
  and [2026-10-26](https://blog.adafruit.com/2026/10/26/ai-assisted-pcb-design-for-kicad-10-using-mcp/).
- r/ClaudeAI: the showcase megathread of April 2026 (Rule 7, 50 karma), through a mirror – the rule's text itself
  is to be read on Reddit before posting.
- [KiCad forum, MCP servers presented](https://forum.kicad.info/t/i-built-an-open-source-mcp-server-for-ai-assisted-kicad-workflows/68678).
- OSHWLab: the programmes as listed on easyeda.com/explore – terms to be read before posting.
- The repository's numbers: `gh api repos/tgd1975/edakit/traffic/…`, `gh repo view`, PyPI's `edakit` 0.0.1 –
  2026-11-01.
