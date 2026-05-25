## Phase 3 Questions

**Purpose:** working planning draft for post-Phase-2 features.  
**Current state:** Phase 2 / GUI is released in `v0.3.4`; Milestones **3a**, **3b**, and **3c** are complete.  
**Planning intent:** define the next group of features before implementation starts.

### Scope and success (what "done" means)

| Number | Question | Answer |
| --- | --- | --- |
| 1.1 | What is the main goal of Phase 3? | Improve fleet observability and UI maturity after the Phase 2 GUI release. |
| 1.2 | What is the first implementation target? | **Milestone 3a — Fleet telemetry**. |
| 1.3 | Should Phase 3 block the existing deploy/inventory workflows? | No. Phase 3 builds on top of the existing stable Phase 2 workflows. |
| 1.4 | Success criterion for the first Phase 3 slice? | Farmer summaries refresh automatically, populate the status bar, and enrich node cards with per-harvester telemetry. |

### Fleet telemetry from `chia farm summary`

| Number | Question | Answer |
| --- | --- | --- |
| 2.1 | Is `chia farm summary` stable enough to parse? | Yes. It is an established command and has been used in scripts for years without issues. |
| 2.2 | Which farmer-level metrics should be shown in the app status bar? | For **Mainnet** and **Testnet** separately: **Last farmed height**, **Total plot count**, **Total plot size**, **Estimated network space**, **Expected time to win**. |
| 2.3 | Which harvester-level metrics should be shown on node cards? | **Plot count**, **Plot size on disk**, and **IP address** derived from the farmer summary. |
| 2.4 | How do we match farmer summary rows to configured nodes? | Match by **IP address** first, then associate that IP with the configured node `host` / resolved node identity. |
| 2.5 | Should the existing fleet summary tab still exist? | Yes. It remains the raw/operator view, while parsed summary data also feeds the status bar and node cards. |

### Refresh and collection behavior

| Number | Question | Answer |
| --- | --- | --- |
| 3.1 | How often should farmer summaries refresh? | Every **120 seconds** to start. |
| 3.2 | Should this replace manual refresh? | No. Keep **Refresh fleet** for immediate refresh; also add periodic refresh. |
| 3.3 | What should periodic refresh update? | Fleet summary tab, parsed telemetry model, node cards, and the status bar. |
| 3.4 | Should refresh intervals be configurable in Phase 3a? | Not initially. Start fixed at 120 seconds. |
| 3.5 | Should periodic refresh continue during deploy? | Prefer **no** during active deploys, unless later testing shows it is safe and low-noise. |

### UI layout and information architecture

| Number | Question | Answer |
| --- | --- | --- |
| 4.1 | How should the bottom status bar be used? | Show compact fleet telemetry from farmer summaries instead of mostly transient text. |
| 4.2 | Should status bar metrics be split by network? | Yes. Show **Mainnet** and **Testnet** distinctly when data is available. |
| 4.3 | Should node cards gain more telemetry rows? | Yes. Add parsed harvester metrics without losing the current deploy/status information. |
| 4.4 | Should the main screen still show the active config path? | No. Remove it from the main view; config actions now live in the menu. |
| 4.5 | Should the fleet summary tab remain mostly raw text? | Yes for Phase 3a. Parsed metrics augment the UI, but the raw text remains useful for operators. |

### Theming and preferences

| Number | Question | Answer |
| --- | --- | --- |
| 5.1 | Should the app support both Light and Dark mode? | Yes. |
| 5.2 | Is theme switching part of Milestone 3a? | No. Treat it as **Milestone 3b — UI maturity / preferences**. |
| 5.3 | Should theme choice persist between launches? | Yes. Persist the user’s theme preference. |
| 5.4 | Should Light mode remain the default? | Yes, unless later changed by user preference. |

### Data model and persistence

| Number | Question | Answer |
| --- | --- | --- |
| 6.1 | Should parsed fleet-summary data be stored permanently in SQLite? | Not required for 3a. Start with an in-memory telemetry model refreshed from farmers. |
| 6.2 | Should we cache the latest farmer summary text? | Yes, at least in memory for the current session. Persistent caching can wait unless needed. |
| 6.3 | Should per-harvester telemetry affect deploy logic? | No. Phase 3 telemetry is display/observability data, not deploy gating. |
| 6.4 | Should Mainnet/Testnet remain a label/filter only? | Yes. Network remains UI/reporting metadata; it does not change config-dir behavior. |

### Packaging, platform, and future scope

| Number | Question | Answer |
| --- | --- | --- |
| 7.1 | Is Linux/macOS controller support part of early Phase 3? | Not the first slice. It remains a later follow-up after telemetry features. |
| 7.2 | Should packaged Windows `.exe` support continue to be maintained? | Yes. Windows packaged builds remain first-class. |
| 7.3 | Are deploy cancel, `.deb` upgrades, and richer log tools part of this planning document? | Richer log tools and settings now belong in **3c**. Deploy cancel and `.deb` upgrade workflow remain later candidates. |

### Operator diagnostics and tooling (Milestone 3c)

| Number | Question | Answer |
| --- | --- | --- |
| 8.1 | Should fleet refresh include node health checks beyond version and farm summary? | Yes. Add both **PING** and **SSH** checks as part of the fleet refresh path. |
| 8.2 | How should node cards signal an unhealthy node? | If either the **PING** test or **SSH** test fails, show a **thick red border** on the card so the failure is obvious at a glance. |
| 8.3 | What real-world scenario is this intended to catch? | Machines like **TARKIN** may hang and stop responding; failed ping/SSH should surface that immediately even before deeper status details are inspected. |
| 8.4 | Should fleet refresh stop if one node fails health checks? | No. Treat health checks as **per-node diagnostics** so the rest of the fleet still refreshes normally. |
| 8.5 | Should the Fleet summary tab gain syntax/color emphasis? | Yes. Add light formatting where it improves scanability: label/value pairs, plot counts, plot sizes, and other obvious value fields. Use restraint and favor readability over heavy coloring. This also includes matching polish in the footer status-bar telemetry. |
| 8.6 | Which operator actions should be added to the Logs tab? | Add **Clear**, **Select All**, **Deselect All**, **Copy to Clipboard**, and **Save as**. |
| 8.7 | Should Logs tab actions honor the current node filter? | Yes. Actions should operate on the **currently filtered log view** only. |
| 8.8 | Should 3c introduce a new Settings menu? | Yes. Add a **Settings** menu after **View** and before **Help** for configurable options such as **refresh interval** and future operator preferences. |
| 8.9 | Are there any small UI consistency items still worth pulling into 3c before release? | Yes. Two good final-polish candidates are: colorizing footer status-bar values to match the Fleet summary treatment, and moving the Fleet summary intro text into an action bar for consistency with the other tabs. |

### Suggested phased delivery

| Milestone | Delivers |
| --- | --- |
| 3a — Fleet telemetry | Parse farmer `chia farm summary`, refresh every 120s, populate status bar, add harvester metrics to node cards, remove config path from main view |
| 3b — Themes and preferences | Light mode / Dark mode, persisted theme choice, UI polish for denser telemetry display |
| 3c — Operator polish and diagnostics | Add ping + SSH health checks to fleet refresh, highlight failed nodes on cards, improve Fleet summary readability, add footer status-bar highlighting, add log actions that honor filters, move Fleet summary intro content into an action bar, and introduce a Settings menu with configurable refresh interval and future operator options |
| 3d — Future ops enhancements | Package/deb upgrade workflow, deploy cancel investigation, broader Linux/macOS controller packaging/testing |

### Notes for implementation

- Build a small parser layer for farmer summaries before wiring UI changes.
- Keep the raw farmer summary text visible even after parsed metrics are added.
- Match harvester rows to configured nodes by IP address first.
- Refresh should reuse the existing fleet-refresh path as much as possible rather than introducing a second independent update pipeline.
- Theme support should be isolated from telemetry work so **3a** can ship independently if desired.
- For **3c** health checks, prefer fast non-blocking diagnostics so one stalled node does not delay the whole refresh loop more than necessary.
- Fleet summary colorization should stay tasteful and readable in both Light and Dark themes.
- Footer telemetry colorization should stay compact and legible; it should complement the badges rather than compete with them.
- The Fleet summary tab should visually match the other tabs by using an action-bar style header where appropriate.
- Logs tab actions should work against the visible filtered subset rather than the full underlying log buffer.

### Phase 3 closeout

- **Recommendation:** treat Phase 3 as complete through **3c** and move the former **3d** items into `docs/PHASE_4_Planning.md`.
- Small polish items originally reviewed between phases were pulled into 3c before release: footer telemetry highlighting and a Fleet summary action-bar header.
