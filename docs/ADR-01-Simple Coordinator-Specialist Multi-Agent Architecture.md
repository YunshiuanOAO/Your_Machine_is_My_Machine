# ADR-01: Simple Coordinator-Specialist Multi-Agent Architecture

Date: 2026-06-03

Status: Accepted

## Context

The project started as a single procedural pentest loop:

- a top-level agent script ran initial recon;
- one LLM handler parsed scan output, queried RAG, and asked Claude for one next action;
- one action executor ran the selected command after human approval;
- state was passed around as loose dictionaries and saved as JSON history files.

This worked for the prototype, but it is now hard to maintain because scanning, parsing, RAG retrieval, LLM planning, command proposal, command execution, retry logic, and reporting are mixed together.


### Refernece
The useful insight from the Claude multi-agent cookbook is not "make many agents." The useful insight is:

- use one coordinator to decide ordering and handoffs;
- give each specialist a narrow job;
- give each specialist only the context and tools it needs;
- make each specialist return a small structured result to the coordinator;
- keep large intermediate context out of the coordinator's main prompt.

For this project, that means we should avoid one huge pentest prompt that sees every scan artifact, every RAG chunk, every failed command, and every tool. We should also avoid over-engineering a large agent platform before the system needs it.

## Decision

We will refactor toward a small coordinator-specialist architecture.

For v1, the system will have one coordinator and three specialist roles:

- `recon_agent`: deterministic Python scanner/parser that produces a normalized recon report.
- `decision_coordinator`: LLM-backed planner that ranks findings and creates exploit tasks.
- `exploit_agent`: LLM-backed worker that handles one exploit task at a time and proposes commands.

RAG lookup, command execution, approval, and reporting will remain local services instead of separate agents unless they become complex enough to justify promotion.

We will use LangGraph only as a lightweight workflow router and state container. The graph should stay small: recon, decision, exploit task loop, approval/execution, aggregation, report. LangGraph is useful here because it makes state transitions and retry routes explicit.

We will not make Claude Managed Agents the default runtime for v1. The cookbook pattern is valuable, but Managed Agents add a remote session/environment model that is more than this project currently needs. We may evaluate Managed Agents later for read-only research specialists, but target-affecting command execution must remain local and controlled by `pentestagent/services/executor.py`.

## What "Subagent Owns Its Session" Means

Each exploit subagent gets its own isolated working context for one task. It does not share a giant conversation history with other exploit attempts.

An exploit-agent session contains only:

- the target IP;
- the relevant service and port;
- the selected CVE or attack hypothesis;
- the small set of RAG snippets needed for that task;
- prior attempts for that same task;
- the command tools it is allowed to propose.

It returns only a structured result to the coordinator. The coordinator does not need the full scratchpad, raw RAG dump, or every intermediate thought.

In v1 this "session" can be implemented locally as a per-task prompt/context object plus a per-task log file. It does not have to be a Claude Managed Agent session.

## State And Message Protocol

The project owns the message schema. Agents may propose commands, but only local validation, human approval, and `pentestagent/services/executor.py` may execute them.

```python
from typing import Literal, Optional, TypedDict
from pydantic import BaseModel, Field


class ServiceFinding(BaseModel):
    port: int
    service_name: str
    product: str | None = None
    version: str | None = None
    notes: list[str] = Field(default_factory=list)


class ReconReport(BaseModel):
    target_ip: str
    services: list[ServiceFinding] = Field(default_factory=list)
    web_paths: list[dict] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


class ExploitTask(BaseModel):
    task_id: str
    target_ip: str
    service_name: str
    port: int | None = None
    cve_id: str | None = None
    hypothesis: str
    confidence_score: int
    context_snippets: list[str] = Field(default_factory=list)


class CommandProposal(BaseModel):
    task_id: str
    action_type: Literal["enumerate", "exploit", "privilege_escalation", "stop"]
    tool: str
    args: list[str]
    risk_level: Literal["low", "medium", "high"]
    timeout_seconds: int = 300
    requires_interactive: bool = False
    reasoning: str
    expected_success_signal: str


class CommandResult(BaseModel):
    command_id: str
    task_id: str
    return_code: int | None
    stdout_path: str | None = None
    stderr_path: str | None = None
    summary: str


class ExploitResult(BaseModel):
    task_id: str
    status: Literal["success", "failed", "retry", "blocked"]
    summary: str
    evidence: dict = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)


class PentestState(TypedDict):
    target_ip: str
    run_id: str
    retry_count: int
    max_retries: int
    recon_report: Optional[ReconReport]
    exploit_tasks: list[ExploitTask]
    command_results: list[CommandResult]
    exploit_results: list[ExploitResult]
    final_report: Optional[dict]
```

Command proposals use `tool` plus `args`, not a raw shell string. The executor is responsible for building the final command from allowlisted tools and validated arguments.

## Architecture

```mermaid
flowchart TD
    CLI["Operator CLI"]:::main
    RECON["Recon Agent<br/>scan + parse artifacts"]:::recon
    COORD["Decision Coordinator<br/>rank findings + create tasks"]:::decision
    RAG["RAG Service<br/>small context snippets"]:::service
    EXP["Exploit Agent Session<br/>one task, scoped context"]:::exploit
    APPROVAL["Human Approval"]:::approval
    EXEC["Local Command Executor<br/>validate + run allowed commands"]:::executor
    AGG["Aggregator<br/>success, retry, blocked"]:::decision
    REPORT["Reporter<br/>final report"]:::report
    END(["END"]):::terminal

    CLI -->|"target + config"| RECON
    RECON -->|"ReconReport"| COORD
    COORD -->|"query needs"| RAG
    RAG -->|"snippets"| COORD
    COORD -->|"ExploitTask"| EXP
    EXP -->|"CommandProposal"| APPROVAL
    APPROVAL -->|"approved"| EXEC
    APPROVAL -->|"rejected"| AGG
    EXEC -->|"CommandResult"| EXP
    EXP -->|"ExploitResult"| AGG
    AGG -->|"retry available"| COORD
    AGG -->|"done"| REPORT
    REPORT --> END

    classDef terminal fill:#F6F6F6,stroke:#777,stroke-width:1px,color:#222
    classDef main fill:#E6F1FB,stroke:#378ADD,stroke-width:1.5px,color:#042C53
    classDef recon fill:#EAF3DE,stroke:#639922,stroke-width:1px,color:#173404
    classDef decision fill:#EEEDFE,stroke:#7F77DD,stroke-width:1.5px,color:#26215C
    classDef service fill:#F0F0F0,stroke:#888,stroke-width:1px,color:#222
    classDef approval fill:#FFF4CC,stroke:#C99500,stroke-width:1px,color:#3B2B00
    classDef exploit fill:#FAEEDA,stroke:#BA7517,stroke-width:1px,color:#412402
    classDef executor fill:#FCEBEB,stroke:#E24B4A,stroke-width:1.5px,color:#501313
    classDef report fill:#E8F0F0,stroke:#4D8585,stroke-width:1px,color:#153B3B
```

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator CLI
    participant RA as Recon Agent
    participant DC as Decision Coordinator
    participant RG as RAG Service
    participant EA as Exploit Agent Session
    participant HA as Human Approval
    participant EX as Command Executor
    participant AG as Aggregator

    OP->>RA: target_ip
    RA-->>DC: ReconReport
    DC->>RG: focused queries for likely findings
    RG-->>DC: small context snippets
    DC-->>EA: one ExploitTask
    EA-->>HA: CommandProposal
    HA-->>EX: approved proposal
    EX-->>EA: CommandResult
    EA-->>AG: ExploitResult

    alt success or no route remains
        AG-->>OP: final report
    else retry_count < max_retries
        AG-->>DC: retry context
    end
```

## Implementation Guidelines

- Keep `pentestagent/main.py` as a thin CLI entry point.
- Keep scan parsing in `pentestagent/tools/parsers.py`, separate from LLM calls.
- Keep RAG as a service function that returns short snippets. Do not pass large document dumps into every agent.
- Keep one LLM adapter module so the rest of the project does not depend directly on Anthropic SDK details.
- Keep command execution local. LLM agents propose `CommandProposal`; they never execute shell commands directly.
- Keep human approval before every target-affecting command in v1.
- Use a per-task exploit-agent context file or log so failures are debuggable without polluting global state.
- Add new agents only when a role needs its own prompt, context, tool scope, and output schema.

## Proposed File Structure

We agree with moving the project into a package, but v1 should stay smaller than a full platform layout. Prefer one obvious home for each responsibility, and split files only when the responsibility is already real in the code.

```text
pentestagent/
├── __init__.py
├── main.py                       # CLI entry point
├── config.py                     # model, retry, timeout, path, env settings
│
├── agents/                       # LangGraph node functions
│   ├── __init__.py
│   ├── recon_agent.py            # runs scan flow and returns ReconReport
│   ├── decision_coordinator.py   # ranks findings and creates ExploitTask objects
│   └── exploit_agent.py          # one scoped exploit-agent session per task
│
├── graph/                        # LangGraph wiring only
│   ├── __init__.py
│   ├── state.py                  # PentestState and graph reducers
│   ├── routing.py                # conditional routes: retry, done, blocked
│   └── builder.py                # StateGraph construction and compile()
│
├── schemas/                      # typed contracts between nodes/services
│   ├── __init__.py
│   ├── findings.py               # ServiceFinding, ReconReport
│   ├── tasks.py                  # ExploitTask, ExploitResult
│   └── commands.py               # CommandProposal, CommandResult
│
├── services/                     # project services, not agents
│   ├── __init__.py
│   ├── llm.py                    # Anthropic/Claude adapter
│   ├── rag.py                    # ChromaDB queries and snippet selection
│   ├── approval.py               # human approval checkpoint
│   ├── executor.py               # validates CommandProposal and runs commands
│   └── reporter.py               # final report writer
│
├── tools/                        # thin wrappers/parsers around external tools
│   ├── __init__.py
│   ├── scan_runner.py            # RustScan -> Nmap -> Dirsearch/WhatWeb orchestration
│   ├── parsers.py                # RustScan/Nmap/Dirsearch normalization
│   ├── rustscan.py
│   ├── nmap.py
│   ├── dirsearch.py
│   ├── whatweb.py
│   └── metasploit.py
│
├── prompts/                      # small role prompts loaded by services/llm.py
│   ├── decision.md
│   └── exploit.md
│
└── observability/                # run artifacts and audit trail
    ├── __init__.py
    ├── artifacts.py              # paths for run outputs, logs, reports
    └── logger.py                 # JSONL event log per run

tests/
├── test_recon_agent.py
├── test_decision_coordinator.py
├── test_exploit_agent.py
├── test_command_executor.py
└── test_graph.py

reports/                          # generated output, gitignored except .gitkeep
└── .gitkeep

.env.example
.gitignore
README.md
requirements.txt
```

For v1, avoid these extra layers unless the need appears:

- `orchestrator/runner.py`: use `pentestagent/main.py` plus `graph/builder.py` first.
- `schemas/messages.py`: do not add a generic `AgentMessage` envelope yet; LangGraph state plus typed payloads are enough.
- `skills/`: use `prompts/` for normal system prompts. Reserve "skills" for richer tool/prompt bundles if we later need that concept.
- `sandbox/`: keep Docker/VPN isolation as deployment infrastructure when ready, but do not block the package refactor on it.
- deeper observability layers: start with `observability/artifacts.py` and `observability/logger.py`; add tracing/metrics only when needed.

Implemented migration mapping:

- CLI and graph invocation live in `pentestagent/main.py`.
- recon execution lives in `tools/scan_runner.py` and dedicated tool wrappers.
- scan artifact parsing lives in `tools/parsers.py`.
- RAG lookup lives in `services/rag.py`.
- Claude JSON calls live in `services/llm.py`.
- command validation/execution lives in `services/executor.py`.

## Output Structure

Generated run output must live under `reports/<run_id>/`. Root-level scan outputs such as `rustscan_output.json`, `dirsearch_output.json`, `network_discovery.txt`, and old `results/agent_state_turn_*.json` files are legacy artifacts and should not be produced by the package.

```text
reports/<run_id>/
├── events.jsonl
├── recon_report.json
├── final_report.json
├── final_report.md
├── scan/
│   ├── rustscan_raw.txt
│   ├── rustscan.xml
│   ├── rustscan_output.json
│   ├── dirsearch_output.json
│   └── whatweb_output.json
└── commands/
    ├── <command_id>.stdout.txt
    └── <command_id>.stderr.txt
```

`observability/artifacts.py` owns run-scoped paths and artifact writes. `observability/logger.py` owns the chronological JSONL event log.

## Alternatives Considered

### Keep the current single-loop agent

Rejected. It is simple, but the main prompt and state object will keep growing until every part of the system knows too much about every other part.

### Full Claude Managed Agents for v1

Deferred. Managed Agents match the cookbook pattern well, but they introduce remote sessions, environments, mounted resources, and provider-specific orchestration. That is not necessary for the first maintainable refactor. They may be useful later for read-only research or report-writing specialists.

### Many specialized agents immediately

Rejected. More agents do not automatically mean better results. For this project, too many roles would make debugging harder. Start with one coordinator and one exploit-agent session per task.

### Raw command strings from the LLM

Rejected. Raw command strings are difficult to validate safely. The LLM should return structured command proposals, and the executor should build the final command from allowed tools and arguments.

## Consequences

Positive:

- Smaller prompts and cleaner context boundaries.
- Easier testing because each role has a typed input and output.
- Less duplicated reasoning because the coordinator handles routing and specialists handle work.
- Safer execution because commands pass through schema validation and human approval.
- Simpler migration path from the current codebase.

Negative:

- Requires writing and maintaining schemas.
- Adds some workflow structure before all agents exist.
- Per-task sessions/logs add bookkeeping.
- Claude Managed Agents are not used immediately, so the project does not get their remote session features in v1.

## Guardrails

- Use only on authorized lab, CTF, class, or owned targets.
- All target-affecting commands require human approval in v1.
- The executor must validate tool names and arguments before running anything.
- Interactive commands are blocked in v1; add them later only behind explicit TTY/session handling and stronger operator controls.
- The graph should fail closed when an agent returns malformed output.
- Store command output as artifacts and pass summaries back to agents.
- Do not leak API keys, VPN details, local secrets, or sensitive file paths into reports.
