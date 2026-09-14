# Claude engineering entry point

@AGENTS.md

The imported file is the common repository engineering contract.
This entry point adds no permissions or separate completion workflow.

## Optional Graphify navigation

When `graphify-out/graph.json` exists and `graphify` is available, use scoped
`graphify query`, `path` or `explain` calls for codebase questions; use its wiki
index for broad navigation when present. Read the full graph report only when
needed. After code changes, update an existing graph with `graphify update .`
when available. Otherwise use repository search and source inspection. Do not
install Graphify or create a graph just to satisfy this optional step.
