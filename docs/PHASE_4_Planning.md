## Phase 4 Questions

**Purpose:** planning draft for post-Phase-3 enhancements.  
**Current state:** Phase 2 is complete, and Milestones **3a**, **3b**, and **3c** are complete.  
**Planning intent:** carry forward the former Phase 3d candidates, decide milestone order for the next phase, and create a clean place to capture additional future ideas.

### Scope and recommendation

| Number | Question | Answer |
| --- | --- | --- |
| 1.1 | Should the remaining **3d** items be finished inside Phase 3? | **Recommendation: no.** Treat Phase 3 as complete after 3c and move the higher-risk operational work into **Phase 4**. |
| 1.2 | Why split here instead of continuing the current phase? | The remaining items are less about UI polish and more about **deployment safety**, **package-management behavior**, **cancellation semantics**, and **controller platform support**. They deserve a separate planning and testing cycle. |
| 1.3 | What is the Phase 4 theme? | **Deployment operations and platform expansion.** |
| 1.4 | What is the overall success criterion? | The app safely handles package-install nodes, has a clearly defined path for stopping/cancelling deployments, and begins broader controller support beyond Windows. |

### Candidate 1: Package / `.deb` upgrade workflow

| Number | Question | Answer |
| --- | --- | --- |
| 2.1 | Why does this belong in a later phase? | Package installs are intentionally excluded from the current git-based deploy path. Supporting them means adding a **second upgrade model** with different safety checks, commands, and failure modes. |
| 2.2 | What would need to happen technically? | Add a package-upgrade workflow for package nodes, detect the correct package manager path, run package-specific prechecks, stop/start services safely, verify versions before/after, and log the process clearly in the GUI. |
| 2.3 | What decisions are needed before implementation? | Whether upgrades should use `apt`, `dpkg -i`, a user-supplied `.deb`, a repo-based package upgrade, or some combination; whether `sudo` is required; and how package sources are validated. |
| 2.4 | What safety concerns exist? | Partial package installs, repo/package mismatches, service restart failures, missing permissions, and unclear rollback if a package install succeeds but Chia does not restart cleanly. |
| 2.5 | What is the recommended first slice? | Start with **Ubuntu/Debian package nodes** already represented in inventory, using a narrow supported workflow with explicit confirmation and strong postchecks. |

### Candidate 2: Deploy cancel / interrupt

| Number | Question | Answer |
| --- | --- | --- |
| 3.1 | Why is deploy cancel not a quick add? | Cancellation is easy to expose in the UI but hard to make **safe**. A cancel request can land while services are stopped, while `install.sh` is mid-run, or after some nodes have succeeded and others have not. |
| 3.2 | What would need to happen technically? | Add cancellation state in the orchestrator, propagate cancellation through async tasks and SSH sessions, define safe cancellation checkpoints, and surface clear final states in the GUI/logs/history. |
| 3.3 | What product decision is required? | Define what **Cancel** means: immediate stop, stop-after-current-step, or best-effort cancel with cleanup. |
| 3.4 | What recovery behavior would be needed? | If cancel happens during a risky step, the app may need to attempt cleanup such as starting services again, recording partial completion, and warning the operator what manual checks are still needed. |
| 3.5 | What is the recommendation? | Treat this as a **design spike first**, then implement only after the cancel semantics are agreed and the failure/recovery behavior is explicit. |

### Candidate 3: Linux/macOS controller support

| Number | Question | Answer |
| --- | --- | --- |
| 4.1 | Why move broader controller support into Phase 4? | The current packaged app story is Windows-first. Cross-platform controller support introduces packaging, path, keyring, icon, signing, and test-matrix work that is best handled as its own stream. |
| 4.2 | What would need to happen technically? | Audit path handling, file dialogs, keyring behavior, ping behavior, icons, startup packaging, and build scripts across Windows/Linux/macOS; then test the GUI and CLI flows on each platform. |
| 4.3 | Should source-run support and packaged builds be treated the same? | No. It likely makes sense to support **run-from-source** first on Linux/macOS, then evaluate native packaging and distribution later. |
| 4.4 | What macOS-specific concerns exist? | App bundle behavior, icon packaging, permissions, notarization/signing if packaged, and any differences in keychain/keyring integration. |
| 4.5 | What Linux-specific concerns exist? | Desktop integration, package/build choices, display-server differences, and validation across likely distributions if packaged. |
| 4.6 | What is the recommended first slice? | First confirm the controller app works **from source** on Linux/macOS, then decide whether native packaged builds are worth the extra maintenance. |

### Suggested Phase 4 milestones

| Milestone | Delivers |
| --- | --- |
| 4a — Package node upgrades | Supported upgrade path for package-install nodes, package-specific prechecks, confirmations, logging, and postchecks |
| 4b — Safe cancel investigation | Finalized cancel semantics, orchestrator design, recovery expectations, and possibly a first operator-facing cancel flow |
| 4c — Cross-platform controller validation | Linux/macOS source-run support, platform audit, and a documented test matrix |
| 4d — Cross-platform packaging and distribution | Optional native packaging/distribution work after 4c proves the controller is stable on non-Windows systems |

### Additional future ideas

| Number | Question | Placeholder |
| --- | --- | --- |
| 5.1 | What additional Phase 4 ideas should be captured next? | Add new ideas here as they are discussed. |
| 5.2 | Should future ideas be grouped by operator workflow, packaging, or automation? | To be decided after the next batch of ideas is collected. |
| 5.3 | Should any future work become a separate Phase 5 instead? | Reassess after 4a–4c are better defined. |

### Notes for implementation planning

- **Recommendation:** close out Phase 3 after 3c and start Phase 4 with a fresh milestone sequence.
- Package-node upgrades should not be mixed into the existing git deploy path without an explicit abstraction for upgrade strategy.
- Cancellation work should be designed around **safe operator outcomes**, not just interrupting threads or SSH commands.
- Cross-platform controller support should start with **source-run validation** before committing to multi-platform packaged builds.
- Add new future-phase ideas to this document as they come up so milestone boundaries stay clear.


### Review Split for Remaining Ideas

#### Pulled into Phase 3 before release

- Footer status-bar value highlighting for both Mainnet and Testnet.
- Fleet summary intro content moved into an action bar for tab consistency.

#### Keep in Phase 4

- Add a **How to** tab. Inside the How to tab, add another tab control for user-guide style documentation. One tab could evolve from the `README.md`, and another could expose release notes.
- Add support for a **local/controller-side Chia node** on the same Windows machine running the app (for example, ARTOO). This would likely require a new notion of `local` vs `remote` execution, a role beyond just `farmer` / `harvester`, and Windows/package-specific status checks instead of the current Linux/SSH assumptions.

#### Likely later than early Phase 4

- Add a guided workflow to create a brand new harvester node for the farm. This would go beyond inventory management and into machine/bootstrap automation: Linux prerequisites, Chia install, harvester configuration, and farm-specific setup steps.
