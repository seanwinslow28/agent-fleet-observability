# Manual tickets — vault file schema

The dashboard reads `vault/00_inbox/tickets.md` (path defined in `build.py:67`)
to populate the Manual chip on the kanban board. The file is parsed by
`lib.readers.read_manual_tickets`, which splits on `## ` headers and matches
plain `-` bullets under each section.

## Expected structure

```markdown
## Todo

- A short ticket title here — assigned: Sean
- Another todo item without an assignee

## In Progress

- Substack post 2 draft — assigned: Sean

## Done

- Reset launchd plist permissions — assigned: meta_agent
```

## Rules

- Section headers MUST be `## Todo`, `## In Progress`, `## Done` (case-insensitive).
- One ticket per `- ` bullet. Sub-bullets are ignored.
- Optional ` — assigned: {agent}` suffix sets the `assigned_agent` field.
- Empty file → Manual chip shows `0`. That is the correct behavior, not a bug.

The dashboard rebuilds at 06:00 ET daily, or run `make build` from this repo
for an on-demand render.
