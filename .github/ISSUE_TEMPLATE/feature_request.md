---
name: Feature request
about: Suggest a new joke, rule, module behavior, or interface for NED
title: "[feature] "
labels: enhancement
assignees: ''
---

## The joke or analysis gap you want to close

<!--
What is currently unfunny, missing, or under-explained? Describe the pattern of
over-interpretation or self-denial that NED should handle better.
-->

## Proposed behavior

<!-- What should NED do? Include example input and the verdict/score you expect. -->

## Which module it belongs to

<!-- Tick one (or more) and say where in the tree it lives. -->

- [ ] PED (Positive Evidence Denier)
- [ ] NEA (Negative Evidence Amplifier)
- [ ] Semantic Escape
- [ ] Asymmetry
- [ ] FNBP
- [ ] UI
- [ ] CLI
- [ ] API
- [ ] rules

<!-- Remember: rules are data. Most detection and explanation changes belong in
     ned/app/rules/*.json, not in Python. -->

## Does it require a new dependency?

**Yes / No:**

<!-- If yes: which dependency, and why can't it be done with the standard library
     plus the existing stack? NED is local-first, fully offline, with no
     telemetry, no analytics, no trackers, no database, no accounts, and no paid
     APIs. -->

## Would it break NED's "we never claim to read minds" rule?

**No** <!-- this must be "no" for the request to be accepted -->

<!-- Explain briefly why the proposal stays inside "possible signals and
     alternative hypotheses" and never asserts anyone's real feelings. If you
     answered "yes", NED is not the right project for this feature. -->
