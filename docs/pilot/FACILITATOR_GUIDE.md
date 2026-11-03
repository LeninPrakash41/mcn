# Running the MCN Student Pilot

A pilot with 5–10 students tells you what blocks real learners before a wide
launch. This guide covers preparation, two sessions, what to observe, and how
to turn the results into fixes.

## Goals

1. Can a student go from nothing to a running app on their own laptop?
2. Which steps, errors or concepts cause them to get stuck, and for how long?
3. Would they choose MCN for their next project?

## Before the pilot (1 week ahead)

- [ ] Pick 5–10 students with mixed experience (some who know Python or JavaScript, some beginners).
- [ ] Send the [Starter Guide](STARTER_GUIDE.md) and ask them to complete **section 1 (install)** before day one.
      Install problems are the most valuable thing to learn about, so ask them to note anything that went wrong.
- [ ] Try the install yourself on a clean machine (Windows and macOS if you can).
- [ ] Decide how feedback reaches you. The in-app feedback button saves reports locally, and sends them to you
      if `MCN_FEEDBACK_ENDPOINT` points at the receiver in [`backend-telemetry-sample/`](../../backend-telemetry-sample/).
- [ ] Print or share the [feedback form](FEEDBACK_FORM.md).

## Session 1 — Foundations (3 hours)

| Time | Activity |
|---|---|
| 0:00 | Welcome. Fix any install problems together and **write each one down**. |
| 0:20 | Tour of MCN Studio (10 min, from the Starter Guide). |
| 0:30 | Exercises 1–3, individually. Exercise 3 is about reading errors. |
| 1:45 | Break |
| 2:00 | Exercise 4 (database) |
| 2:40 | Five-minute feedback round: "What confused you most today?" |

## Session 2 — Build an app (3–4 hours)

| Time | Activity |
|---|---|
| 0:00 | Exercises 5–6: API, then UI and preview |
| 1:30 | Exercise 7: AI triage |
| 2:00 | Capstone (exercise 8) in pairs |
| 3:30 | Demos (3 minutes per pair) and the [feedback form](FEEDBACK_FORM.md) |

## What to observe

Write down **every time a student is stuck for more than 2 minutes**:

| Time | Student | Exercise | What they were trying to do | What blocked them | How it got resolved |
|---|---|---|---|---|---|

Pay special attention to:

- **Error messages**: did they understand the message and hint without asking you? Copy the exact message.
- **Syntax surprises**: what they typed expecting it to work (often Python or JavaScript habits).
- **Studio**: buttons they couldn't find, panels they didn't notice.
- **Silent failures**: the program ran but did the wrong thing, with no error. These are the worst bugs.

Resist helping for the first two minutes; the point is to find where they get stuck.

## Metrics to collect

| Metric | Target for a wide launch |
|---|---|
| Install succeeded without help | ≥ 90% |
| Exercises 1–4 completed in session 1 | ≥ 80% |
| A working app in Preview (exercise 6) | ≥ 80% |
| Errors understood without help (from observation log) | ≥ 70% |
| "Would use MCN again" (form, 4–5 out of 5) | ≥ 70% |

## After the pilot

1. Group the observation log by cause: install, error messages, language, Studio, docs.
2. File one issue per cause, with the exact error text and the student's code.
3. Fix anything that blocked two or more students before the wide launch.
4. Add a test for every bug found (`tests/`), so it stays fixed.
5. Re-run the starter guide on a clean machine after the fixes.
