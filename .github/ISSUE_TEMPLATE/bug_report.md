---
name: Bug report
about: Something in NED misbehaves — wrong score, crash, weird verdict
title: "[bug] "
labels: bug
assignees: ''
---

<!--
Thanks for the report. NED is satire; bugs are still real. Please fill in the
sections below.
-->

## What happened

<!-- Describe the actual behavior. Paste the error output or the surprising verdict. -->

## What you expected

<!-- Describe what you expected instead, and why. -->

## Exact input text and mode

**Mode:** `normal` / `scientific` / `extreme`

**Input text:**

```
<paste the message or event description you analyzed>
```

> **NEVER paste someone else's private chat logs.** Anonymize them first: change
> names, timestamps, and any identifying detail, or rewrite the message as a
> generic equivalent that still triggers the bug. If the report must contain a
> real conversation, reduce it to the minimum fragment that reproduces the
> problem. Reports containing identifiable third-party messages may be edited or
> closed.

## Reproduction steps

1.
2.
3.

<!--
If you used the CLI, include the exact command, e.g.:
ned analyze "我想你了" --mode scientific --json
ned asymmetry --positive "..." --negative "..." --json
If you used the API, include the endpoint and request body.
-->

## Environment

- OS: <!-- e.g. Windows 11 24H2, Ubuntu 24.04, macOS 15 -->
- Python version: <!-- python --version -->
- `ned version` output:
- Install method: <!-- pip install -e ".[dev]" in a venv / other -->

## Anything else

<!-- Screenshots, related rules/*.json pack edits, whether the bug also happens in `ned demo` or `ned examples`, etc. -->
