# BenchLedger — Requirements v1.0

Signed off Nov 7, 2026 · twodogstar

## Overview

BenchLedger (formerly BenchWorks) is a personal electronic lab notebook for a home electronics and metrology bench. Its main job is to keep what was measured, what was observed and what is only suspected clearly apart, and to tie each to the raw data behind it.

**Key decision: the notebook and the bench software stay separate.** BenchLedger records knowledge (projects, observations, hypotheses, faults, runs, data). The GPIB/Python bench software controls instruments and writes data. They connect only through a shared file format, the *run package* (see [Run package format](#run-package-format)). An overnight logging run never depends on the notebook being up, and each project can change on its own schedule.

**Scope for v1:** a single user on the MX Linux PC, with the existing project content brought over by a one-time import. The public portfolio is a separate site. BenchLedger only exports content for it.

## Users and roles

v1 has one user, the owner, and needs no login while it runs only on the local machine. The data is built so other users can be added later without changes.

| Role | Who | Can do | When |
| --- | --- | --- | --- |
| Owner | You | Everything, including settings, backups and user management | v1 |
| Collaborator | Possibly one friend | Create and edit projects, runs and entries | v2 |
| Reviewer | Friends in test & development and analog engineering | Read everything shared with them; comment on entries, runs and faults | v2 |

- **U1:** Every entry, edit and comment records its author from day one, even before logins exist.
- **U2:** Projects can be shared per person later (e.g. a reviewer sees the ADR1399 project but not the CH341 one). Not needed in v1, but nothing in the design should prevent it.

## Functional requirements

v1 is built around three priorities: measurement data, the logger hookup through run packages, and proper measurements. Edit history is also in v1. Everything below is tiered Must / Should / Could / Won't.

### Must have (v1)

| ID | Requirement |
| --- | --- |
| M1 | **Projects** with goal, current state, setup, wiring, parts, stage, priority and linked instruments. |
| M2 | **Dated notebook entries** (observation, hypothesis, decision, note) with evidence label and source. Add-only: edits keep the full history, so what was believed on a given date can always be recovered. |
| M3 | **Hypotheses** with a status (Untested, Testing, Supported, Rejected), plus **open questions**. |
| M4 | **Fault tracker**: symptom, status, evidence label, next test that would tell the explanations apart, resolution. |
| M5 | **Next-step tasks** per project. |
| M6 | **Instrument register**: model, ID string, serial, firmware, interface and GPIB address, capabilities, condition, and a dated log of faults and self-test results. |
| M7 | **Runs on their own page**: type, method, configuration, environment, instruments with their settings, checklist, observations, limitations, attached data. |
| M8 | **Run package import** by upload. Raw files are stored exactly as received, with a checksum. The current logger CSV format imports as-is. |
| M9 | **Time-series charts**: several channels (volts, ppm, temperature, humidity) on a shared time axis, with zoom and pan. Bus errors, gaps and notes are marked on the chart. Long runs are thinned for display only. |
| M10 | **Computed statistics** for a whole run or a selected window: mean, σ, peak-to-peak, ppm deviation from a chosen baseline, drift rate, Allan deviation, and tempco when a temperature channel exists. |
| M11 | **Summary measurements**: value, ± uncertainty, unit, n, σ. Metric names come from a managed list so comparisons line up. |
| M12 | **Photos and screenshots**, stored on disk and linked to a project, run or entry. |
| M13 | **Templates** for experiments and troubleshooting, with checklists. |
| M14 | **Markdown reports** per project or run, with charts included as images. |
| M15 | **Search** across projects, entries, runs, faults and instruments. |
| M16 | **Backups**: automatic daily backup of the database and files, full export, and a tested restore. |

### Should have (v1.x)

| ID | Requirement |
| --- | --- |
| S1 | **Evidence links**: a hypothesis to the run that tests it, a fault to the runs that reproduce it, an observation to its data. |
| S2 | **Run comparison**: overlay two or more runs, lined up by elapsed time or clock time, e.g. ADR1399 before and after an enclosure. |
| S3 | **Drop-folder import**: run packages written to a watched folder import automatically. |
| S4 | **Document library**: datasheets and instrument manuals, linked to instruments and parts. |
| S5 | **Tags** on projects, runs and entries. |
| S6 | **Calibration and verification records** per instrument: date, method, reference used, result. |

### Could have (v2)

| ID | Requirement |
| --- | --- |
| C1 | Logins, roles and comments for collaborators and reviewers. |
| C2 | Phone capture at the bench: a photo plus a one-line observation added to the current project. |
| C3 | Self-hosting reachable from outside the home network, once the network is locked down. |
| C4 | Portfolio export: a project as Markdown plus images, for the separate portfolio site. |
| C5 | Live data sent from the logger during a run. |
| C6 | Multi-reference scanner runs: many references switched by relays into one meter, each stored as its own channel. |

### Won't have (this project)

- Instrument control or test sequencing (that belongs to the GPIB bench software).
- Hosting the public portfolio.
- Parts inventory and purchasing.

## Non-functional requirements

The system has to run comfortably on the MX Linux PC (Phenom II X6), keep raw data untouched, and be ready to self-host later without a rewrite.

| ID | Area | Requirement |
| --- | --- | --- |
| N1 | Hosting | Runs on the MX Linux PC and starts with one command. Reachable only from that machine by default; home-network access is a config switch. |
| N2 | Performance | Handles continuous runs of at least 3 months at about 3 s per reading (about 2.3 million readings per channel), though most runs last a few days. Charts stay responsive by thinning points for display; stored data is never thinned. |
| N3 | Data integrity | Raw files are kept exactly as received, with a SHA-256 checksum. Derived numbers are always recalculated from raw data, never typed over it. |
| N4 | Open formats | SQLite database plus a plain files folder. Everything can be read without BenchLedger. |
| N5 | Backups | Several automatic, encrypted backups following the 3-2-1 rule: a local USB copy and an off-site cloud copy, plus one-click full export. See [Backup plan](#backup-plan). |
| N6 | Format changes | The data format is versioned and changes go through migrations. The app never silently resets or discards data it can't read. |
| N7 | Time | Timestamps are stored in UTC with the source offset kept. Display is local time. Readings crossing a daylight-saving change stay in correct order. |
| N8 | Self-host readiness | Settings in a config file, no hard-coded paths, works behind a reverse proxy with HTTPS, and room for logins (C1) without restructuring. |
| N9 | Security baseline | User text can never run as code in the page (escape all output); file uploads are checked by type and size; no internet access is needed to run. |
| N10 | Maintainability | Normal source files under git, automated tests for import and statistics, and no single file holding the whole app. |

**Sizing from the Oct 31 ADR1399 CSV:** one reading every 3.36 s (NPLC 100 with autozero on), which is about 1,070 readings per hour. A 10-hour night is about 10,700 readings per channel, and a 30-day continuous run about 770,000. A 3-month run is about 2.3 million readings per channel, which N2 covers.

## Backup plan

Backups follow the 3-2-1 rule: three copies, on two kinds of media, one off-site. Every copy is encrypted, and the backup job can't delete its own history. Failures raise alerts, and restores are tested on a schedule.

| Copy | Where | Encryption | Schedule | Protects against |
| --- | --- | --- | --- | --- |
| 1. Live | MX Linux PC | Optional disk encryption | Continuous | — |
| 2. Local | USB drive | Encrypted drive (LUKS) plus backup-tool encryption | Nightly while attached, at least weekly | Disk failure, accidental deletion, a bad migration |
| 3. Off-site | Cloud object storage (e.g. Backblaze B2 or rsync.net) | Encrypted on the PC before upload; the provider never sees readable data | Nightly | Fire, theft, flood, losing everything in the house |

Optional extra: rotate two USB drives and keep one away from the house, which gives a second off-site copy without the cloud.

| ID | Requirement |
| --- | --- |
| B1 | **Tool:** an encrypting backup tool that only stores changes (e.g. restic or BorgBackup). Only changed data uploads, and any past day can be restored. |
| B2 | **Consistent snapshot:** BenchLedger writes a consistent copy of the database before each backup, so a backup never catches it mid-write. |
| B3 | **What's included:** database, files folder (run packages, photos, documents), config, and the bench logger's output folder. Source code lives separately in its git repository. |
| B4 | **Can't be wiped:** the cloud credentials on the PC can add backups but not delete or overwrite them (an append-only key or object lock). Old backups are pruned only with a separate admin credential, used deliberately. A compromised PC can't destroy the backup history. |
| B5 | **Retention:** 7 daily, 4 weekly, 12 monthly, and one per year kept indefinitely. The data is small, so long retention is cheap. |
| B6 | **Keys:** the encryption password is kept in a password manager and on paper in a separate place. Without it the backups can't be read, and there is no recovery. |
| B7 | **Monitoring:** the dashboard shows the last successful backup for each copy and warns after 48 hours without one; email or push alerts are optional. Silent failure is the most common way backups fail. |
| B8 | **Restore testing:** a monthly automatic integrity check plus a sample restore compared by checksum, and a full restore drill to a spare folder every quarter, logged in BenchLedger. |

**Size and cost:** one night of logger CSV is roughly 0.5 MB, so photos will make up most of the volume. Expect a few GB after years of use. Cloud cost should be small; current pricing gets confirmed when the provider is chosen.

## Measurement data and metrology conventions

Standard practice for voltage-reference work is to log every reading continuously at long integration times, record temperature alongside, and report noise and drift separately. Averaging is done afterward, never in the logger. BenchLedger follows that: it stores raw readings and calculates everything else.

**Sampling and duration**

- **Integration:** NPLC 10–100 with autozero on is normal for references. The current setup (NPLC 100, autozero on, 10 V range, Zin >10 GΩ) is already in line with it.
- **Interval:** log every reading at the meter's natural rate (about 3.4 s here). Means over 1 or 10 minutes can always be calculated later; a logger that averages throws information away for good.
- **Duration:** minutes to hours shows short-term noise; days to weeks shows drift and temperature effects. Long-term stability is quoted in ppm per 1,000 hours, which takes weeks or months of logging.
- **Warm-up:** meter specs generally assume a warm-up period (1 hour for the 34401A). Runs mark a warm-up window that statistics leave out by default.
- **Environment:** temperature at the reference and near the meter, plus humidity, logged with the same timestamps as the voltage.

**Statistics BenchLedger calculates (M10)**

| Statistic | What it tells you | Caveat |
| --- | --- | --- |
| Mean | Central value over a window | Only meaningful with the window stated |
| σ (std dev) | Noise, when taken over a short window | Over a whole run it mixes noise with drift and keeps growing as the run gets longer |
| Peak-to-peak | Worst-case spread | Depends heavily on window length; always quote the window |
| ppm from baseline | Change relative to a reference value | The baseline must be explicit: first reading, mean of the first hour after warm-up, or a nominal value |
| Drift rate | Slope of a straight-line fit, in ppm/hour or ppm/day | Assumes a straight line; check the residuals |
| Allan deviation vs τ | Separates white noise (falls with averaging) from flicker and drift (flat or rising), and shows the best averaging time | Needs long runs; the standard tool for references and oscillators |
| Tempco | ppm/°C from regressing voltage against temperature | Shows correlation, not cause; feeds a hypothesis, not a conclusion |

Allan variance for averaging time τ, where ȳₖ is the k-th average over a block of length τ:

```
σ²_y(τ) = ½ ⟨ (ȳ_{k+1} − ȳ_k)² ⟩
```

**About the current console line** (`#10159  7.0548023 V  Δ +4.607 ppm  σ 0.632 ppm  p-p 5.372 ppm`): it works well as a live display and should stay. But σ and p-p are cumulative over about 9.5 hours, so they include drift rather than measuring noise. For comparison, the first 11 minutes of the Oct 31 file give σ = 0.25 ppm and p-p = 1.08 ppm (200 readings). Δ is measured from the very first reading, which falls inside warm-up. BenchLedger recalculates all of these from raw data over windows you choose.

**Meter vs reference.** With one 34401A, every reading combines the reference with the meter's own drift and temperature effects, and those are of the same order as the effects being looked for. The standard ways to separate them are to compare two references through the same meter (meter drift cancels in the difference, which is C6) or to cross-check against a second meter good enough to resolve ppm. The Fluke 45's resolution is too coarse for ppm-level work. **Requirement:** a run can hold several channels from several instruments, plus calculated channels such as A − B.

## Run package format

The current logger CSV is a good starting point. It records the instrument ID, settings and start time, and every reading at full precision with an elapsed-seconds column. It lacks time zones, structured metadata, an end marker and a place for errors. The run package keeps the CSV and adds those. The exact format is specified in the [design](design.md#run-package-spec-v1-draft).

**What the Oct 31 file does well**

- A comment header with `*IDN?`, settings and start time.
- `elapsed_s` gives a steadily increasing clock that doesn't depend on wall-clock time.
- Full-precision volts (8 decimal places); nothing rounded or averaged.

**Gaps found**

| Gap | Why it matters |
| --- | --- |
| Timestamps have no time zone | US daylight saving ended at 2:00 AM on Nov 1, 2026, the night after this run started. In an overnight run, the 01:00–02:00 hour would appear twice. `elapsed_s` saves the ordering, but timestamps should carry an offset or be in UTC. |
| Settings are one free-text line | Range, NPLC and autozero can only be pulled out by guessing at the text. Structured key/value fields import reliably. |
| Missing context fields | No GPIB address, front/rear terminals, which reference is being measured, or script name and version. |
| No environment channels | Temperature and humidity are planned; columns for them need to be defined. |
| No error or event record | The logger is meant to log bus errors and keep going, but a skipped reading currently leaves only a jump in `elapsed_s`. |
| No end marker | Can't tell a finished run from one that crashed or is still running. |
| `delta_ppm` has an unstated baseline | It's measured from the first reading. Keep it for convenience, but BenchLedger recalculates it from a baseline you choose. |
| `interval 0.0s` vs the actual 3.36 s | Record both the requested and the measured interval. |

**Requirements**

- **R1:** Existing logger CSVs import as-is. Their timestamps are read as America/Los_Angeles local time, and `elapsed_s` decides the order.
- **R2:** New run packages carry structured metadata, time-zone-aware timestamps, an events record and an end status.
- **R3:** Each package carries a format version, so old packages keep importing as the format changes.
- **R4:** Gaps in data (a jump in elapsed time well beyond the measured interval) are detected on import and shown on the chart, even when no event explains them.
- **R5:** Importing the same package twice is detected by checksum and doesn't create a duplicate run.
- **R6:** The format is documented in a short spec owned by both projects, so the GPIB software can write it without depending on BenchLedger.

## Decisions at sign-off

| Question | Decision |
| --- | --- |
| Requirements | Signed off, Nov 7, 2026. |
| Temperature and humidity logging | Same file as the voltage (decided in design). |
| Backups | Several encrypted copies: a local USB drive plus an off-site cloud copy. Provider not yet chosen. |
| Longest run | Months are possible; most runs last a few days. |
| Collaborator access (C1) | A possible future upgrade, not planned yet. |
