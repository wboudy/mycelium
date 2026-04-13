## 1. Goals

The system MUST read local Markdown files and parse task list items into a canonical task schema. It MUST generate a weekly plan summary with priorities and due dates while keeping human-edited Markdown as the source of truth. It MUST NOT destructively edit original task files. Parsing and planning SHOULD be deterministic for a given input set and selected week.

## 2. Architecture

A local CLI tool MUST operate on a user-specified root directory. It MUST include: (a) file scanner (`.md` only), (b) Markdown task parser, (c) task normalizer, (d) weekly planner, and (e) plan renderer. The tool MUST NOT make network calls and MUST write outputs only to a separate plan artifact.

## 3. Data Model

A Task MUST include: `task_id` (stable hash of `source_path + line_no + raw_text`), `source_path`, `line_no`, `title`, `completed` (bool), `due_date` (optional `YYYY-MM-DD`), `priority` (`P0|P1|P2`, default `P2`), and `tags` (zero or more `#tag`). A WeeklyPlan MUST include: `iso_week` (`YYYY-WW`), and ordered lists `due_this_week`, `overdue`, and `unscheduled`.

## 4. Execution Flow

The tool MUST scan recursively for `.md` files, parse lines matching `- [ ]` or `- [x]` outside fenced code blocks, extract metadata tokens `due:YYYY-MM-DD`, `P0|P1|P2`, and `#tags`, then normalize and filter to incomplete tasks. It MUST bucket tasks relative to the selected `iso_week`, sort by `(priority, due_date, source_path, line_no)`, and render a Markdown plan file.

## 5. Acceptance Criteria

* Given a file containing `- [ ] Pay rent due:2026-03-01 P0 #finance`, the parsed Task MUST set `due_date=2026-03-01`, `priority=P0`, `tags` includes `finance`, and `completed=false`.
* Running the tool twice on unchanged inputs and the same `iso_week` MUST produce byte-identical plan output.
* The tool MUST NOT modify any source `.md` file (content hash unchanged before vs. after).
* Tasks with `- [x]` MUST NOT appear in the weekly plan output.
