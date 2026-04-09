# Ariadne Memory Positioning

## Purpose

This document places Ariadne on the current agent-memory landscape and makes an explicit positioning call.

The main question is not "how do we copy Codex or Claude Code memory?" It is:

- what is Ariadne today
- what would Ariadne become if we execute the current backlog
- what corner of the market and design space should Ariadne try to dominate

## Source Set

This analysis uses:

- Ariadne's current scope in [README.md](./README.md)
- Ariadne's current backlog and direction in [ideas.md](./ideas.md)
- the `agentic-memory` research collection:
  - [README](https://raw.githubusercontent.com/lhl/agentic-memory/main/README.md)
  - [ANALYSIS.md](https://raw.githubusercontent.com/lhl/agentic-memory/main/ANALYSIS.md)
  - [ANALYSIS-academic-industry.md](https://raw.githubusercontent.com/lhl/agentic-memory/main/ANALYSIS-academic-industry.md)

This is a synthesis document, not a full literature review of every referenced system.

## Ariadne Today

Today Ariadne is best described as:

- a repository intelligence and context-packing system
- with explicit graph structure
- plus a durable memory layer
- exposed over CLI, API, and MCP

That is visible in the current product shape:

- repo registration, indexing, parsing, graph storage, memory CRUD, retrieval, and packed context in [README.md](./README.md)
- code/doc/config/test graphing and file-symbol-memory retrieval in [ideas.md](./ideas.md)
- MCP tools focused on `search`, `retrieve`, `pack_context`, `trace`, `graph`, and memory CRUD rather than full assistant-state orchestration

What Ariadne is not yet:

- not a transcript-first memory OS
- not a personal assistant memory surface
- not a full session lifecycle manager
- not a temporal or versioned truth system
- not a write-gated, poisoning-hardened memory governance system

So on the `agentic-memory` map, Ariadne currently sits closer to:

- graph-first retrieval infrastructure
- coding-task context assembly
- software-work memory primitives

than to:

- Codex/Claude-style assistant continuity memory
- MemGPT-style memory operating system metaphors
- broad personal-memory products

## Ariadne If We Execute The Current Backlog

If Ariadne adds the backlog already on the board, especially:

- conversation/session ingest
- archived thread ingest
- source metadata on imported memories
- reviewed link workflows
- commit nodes
- stronger MCP ergonomics
- better provenance and trust surfaces

then Ariadne moves into a much stronger category:

- evidence-backed software memory substrate

That future Ariadne would still not be "another Codex memory."

Instead it would become:

- a system that can ingest code, docs, config, tests, commits, decisions, incidents, and archived threads
- derive durable typed memory from those sources
- link them into an explicit graph
- retrieve them with provenance, confidence, and reviewability
- compile compact task-specific context for an agent or human

That is a different product thesis from "remember my preferences and workflow habits."

## The Positioning Call

The corner Ariadne should try to dominate is:

- evidence-backed long-term memory for software work

Not:

- generic consumer assistant memory
- coding-agent convenience memory alone
- another vector-memory backend with thin developer ergonomics

The core job should be:

- for a real engineering task, find and assemble the exact code, docs, config, tests, commits, design notes, incidents, and archived thread knowledge that matter
- keep that retrieval inspectable
- keep durable memory reviewable and reversible
- preserve enough provenance that users can trust what got surfaced

The moat, if this is right, is:

- retrieval quality
- graph correctness
- provenance
- reviewability
- temporal correctness
- benchmark discipline
- trust and operational rigor

## What Ariadne Should Learn From Other Systems

### Good Ideas To Steal

From coding-agent memory systems such as Codex memory, Claude Code memory, ByteRover CLI, and OpenViking:

- typed durable objects instead of a flat bag of notes
- progressive retrieval tiers from cheap local hits to more expensive search
- session promotion flows instead of only ad hoc manual memory writes
- better operator ergonomics for inspecting and editing memory

From graph and memory systems such as Zep, memv, and Hindsight:

- temporal validity and supersession
- evidence vs belief separation
- versioned or corrected memory rather than overwrite semantics
- stronger handling of stale or conflicting durable memory

From benchmarks and research systems such as EverMemBench, StructMemEval, LoCoMo-Plus, TiMem, HiMem, and Nemori:

- evaluate structure, temporal coherence, and long-horizon recall
- segment sessions into episodes before promotion
- consolidate hierarchically instead of storing one giant summary blob
- treat memory as a pipeline, not as a vector database

### Ideas To Avoid Overfitting On

- personal preference memory as the default center of the product
- opaque assistant-specific prompt glue
- a "memory OS" framing that outgrows the actual engineering use case
- adopting storage choices from other systems as ideology rather than as deployment tradeoffs

## What Ariadne Is Competing With

Ariadne is not primarily competing with Codex memory or Claude Code memory on their strongest axis.

Those systems are strongest at:

- keeping an assistant feeling continuous across sessions
- remembering user workflow conventions
- smoothing personal coding ergonomics

Ariadne should instead compete on:

- exactness of engineering retrieval
- quality of code-doc-config-memory linking
- inspectability of why something was retrieved
- ability to act as team-usable durable engineering memory, not just personal agent continuity

## 2x2 Scorecard 1

Axis:

- horizontal: generic assistant memory -> evidence-backed software memory
- vertical: low provenance/review -> high provenance/review

| | Generic assistant memory | Evidence-backed software memory |
| --- | --- | --- |
| High provenance / review | OpenViking | Ariadne with planned backlog, Zep, Hindsight-inspired Ariadne |
| Low provenance / review | Codex memory, Claude Code memory, generic vector memory products | Ariadne today |

Notes:

- Ariadne today already points at software work, but it is still too thin on ingest, review, and temporal truth to fully occupy the upper-right quadrant.
- Ariadne with the current backlog belongs in the upper-right quadrant if provenance and review stay first-class.

## 2x2 Scorecard 2

Axis:

- horizontal: individual convenience -> team system of record
- vertical: lightweight note memory -> structured graph memory

| | Individual convenience | Team system of record |
| --- | --- | --- |
| Structured graph memory | OpenViking, Zep | Ariadne with planned backlog |
| Lightweight note memory | Codex memory, Claude Code memory, ByteRover CLI | Mem0-style shared memory layers |

Notes:

- Ariadne today is between the lower-right and upper-right cells: more structured than note-memory systems, but not yet strong enough on ingest/governance to fully claim "team system of record."
- The current backlog is exactly what pushes it decisively upward.

## 2x2 Scorecard 3

Axis:

- horizontal: retrieval/context packing -> full memory lifecycle
- vertical: software-work specialization -> general-purpose agent memory

| | Retrieval / context packing | Full memory lifecycle |
| --- | --- | --- |
| Software-work specialization | Ariadne today, ByteRover CLI | Ariadne with planned backlog, OpenViking |
| General-purpose agent memory | generic RAG memory layers | MemGPT, Mem0, Supermemory, many benchmark-oriented research systems |

Notes:

- Ariadne today is clearly in the lower-left cell of this chart's top row: software-specialized, but still more retrieval engine than lifecycle manager.
- The current backlog moves Ariadne to the upper-right cell of the top row without requiring it to become a general-purpose memory product.

## Score Summary

Using a simple directional score from `1` to `5`:

- `Software-work specialization`
- `Evidence and provenance`
- `Memory lifecycle depth`
- `Team-usable durability`

| System | Software-work specialization | Evidence and provenance | Memory lifecycle depth | Team-usable durability |
| --- | --- | --- | --- | --- |
| Ariadne today | 5 | 3 | 2 | 3 |
| Ariadne with current backlog | 5 | 5 | 4 | 5 |
| Codex memory | 4 | 2 | 3 | 1 |
| Claude Code memory | 4 | 2 | 3 | 1 |
| ByteRover CLI | 5 | 3 | 3 | 2 |
| OpenViking | 4 | 4 | 4 | 3 |
| Zep | 2 | 4 | 4 | 4 |
| Mem0 | 2 | 3 | 4 | 4 |

These scores are heuristic and only meant to make the positioning easier to discuss.

## Recommendation

The product strategy should stay centered on this sentence:

- Ariadne is the durable memory, retrieval, and context-assembly layer for software work.

That implies:

- do not optimize first for "assistant personality continuity"
- do optimize for reviewable engineering memory with explicit provenance
- do make archived threads, incidents, commits, docs, and code equally first-class retrieval inputs
- do benchmark memory quality the same way we benchmark retrieval quality

## Short Version

Current Ariadne:

- repo intelligence engine with graph retrieval and basic durable memory

Planned Ariadne:

- evidence-backed software memory substrate for agents and humans

Target corner:

- dominate inspectable, reviewable, team-usable long-term memory for engineering work

Not:

- generic assistant memory
- another Codex or Claude Code memory clone
