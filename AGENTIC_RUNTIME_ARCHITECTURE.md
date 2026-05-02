# Agentic Runtime Architecture

## Summary

This repository now uses a single agentic fallback runtime for Moto LLM-backed AWS responses.
The runtime is not a free-form "LLM writes the whole response" path. It is a constrained planner-agent plus deterministic AWS response renderer.

The main goal is:

- keep one runtime path instead of maintaining separate workflow and agentic paths
- let the LLM make only the high-level response plan
- let deterministic code build AWS-shaped payloads from botocore models
- serialize responses with Moto's protocol serializers
- validate parseability, protocol, safety, and AWS output shape before returning
- record latency, token usage, provider metadata, and audit evidence

## Current Request Flow

Entry point:

```text
moto.core.llm_agents.agent.handle_aws_request(...)
```

Runtime flow:

```text
handle_aws_request
  -> extract_session_id_tool
  -> normalize_request_tool
  -> get_world_state_tool
  -> get_session_history_tool
  -> run_agent_loop
       -> build_agent_prompt
       -> OpenAI Responses API direct call
       -> parse_agent_output
       -> build_response_plan_tool
       -> adapt_response_plan
            -> read botocore output shape
            -> generate deterministic field values
       -> serialize_response_tool
            -> Moto AWS protocol serializer
       -> validate_rendered_response_tool
       -> retry at most once if validation fails
  -> add_to_session_history_tool
  -> update_world_state_tool
  -> write audit record
  -> return AWS response body
```

The important boundary is that the LLM does not render the final AWS response body.
The final JSON/XML body is produced by deterministic runtime code.

## Is This a Single Agent?

Yes, in the current implementation the fallback path is a single agentic runtime.

The public handler always calls:

```python
run_agent_loop(...)
```

The older split between a `workflow` path and an `agentic` path has been removed from the active runtime path.
Provider execution is also narrowed to OpenAI Responses API direct calls.
OpenCode/opencode transport and alternate Claude provider paths are not part of the current live benchmark path.

More precisely, the architecture is:

```text
single planner-agent + deterministic AWS shape adapter + deterministic serializer + validator
```

It is intentionally not a multi-agent system.

## Difference From a Plain LLM Call

A plain LLM fallback would ask the model to directly produce the final response body:

```text
request -> prompt -> LLM writes JSON/XML -> return body
```

That is risky for this use case because AWS responses need to match service-specific protocols and output shapes.
The model can easily produce plausible-looking but structurally wrong XML/JSON.

The current runtime instead does this:

```text
request -> LLM writes compact response plan -> deterministic code renders AWS body
```

The LLM output is limited to fields such as:

- intent phase
- response posture
- error mode
- entity hints
- field hints
- environment delta

Then deterministic code handles:

- botocore output shape lookup
- fake but consistent resource value generation
- AWS JSON/XML/query/ec2 protocol serialization
- validation and retry
- audit and benchmark metadata

This gives the LLM room to act like an agent without trusting it to hand-write final AWS wire output.

## Why This Design

### 1. AWS output shape correctness matters

Moto fallback responses must look like real AWS responses.
AWS CLI output examples are backed by botocore service models, so the runtime uses botocore output shapes as the source of truth.

The benchmark now verifies:

- command page URL exists in AWS CLI reference
- `Output` section exists
- botocore service and operation mapping exists
- top-level output members match
- nested structures, lists, maps, and scalar positions match recursively

This caught a real mismatch in `DescribeVolumeStatus`.
The top-level response was correct, but nested fields under `VolumeStatuses[].VolumeStatus.Details[]` were wrong.
The fix was to make nested structure generation compatible with deeper AWS shapes.

### 2. LLM output should be small and cheap

The compact prompt is the default.
It intentionally avoids sending the full botocore schema to the model on every request.
The runtime already has the schema locally and can render the body without asking the model to describe every field.

This reduces input tokens and keeps the model focused on planning.

### 3. Deterministic rendering is easier to test

Response generation is split into testable stages:

- request normalization
- agent plan parsing
- response plan construction
- shape adaptation
- protocol serialization
- validation

This is easier to test than one large prompt whose output has to be trusted directly.

### 4. Retry is bounded

The agent loop retries at most once by default.
There is no open-ended agent loop.
If validation fails, the next prompt includes a compact observation and asks the model to correct the plan.

This prevents runaway cost and avoids hiding structural problems behind repeated model calls.

## Main Code Areas

- `moto/core/llm_agents/agent.py`
  - public fallback handler
  - request/session/world-state orchestration
  - audit logging

- `moto/core/llm_agents/runtime/runner.py`
  - single agent loop
  - calls provider
  - builds response plan
  - renders and validates response

- `moto/core/llm_agents/runtime/planner.py`
  - compact prompt construction
  - model output parser
  - default fallback output

- `moto/core/llm_agents/runtime/provider.py`
  - OpenAI Responses API direct call
  - token usage and response id capture
  - `.env` loading without printing secrets

- `moto/core/llm_agents/shape_adapter.py`
  - botocore output shape traversal
  - deterministic fake field generation
  - nested list/structure handling

- `moto/core/llm_agents/tools/render_tools.py`
  - Moto serializer integration
  - protocol-correct JSON/XML body rendering

- `scripts/benchmark_agentic_runtime.py`
  - 40-command corpus runner
  - AWS CLI reference URL check
  - recursive output shape validation
  - live OpenAI benchmark
  - latency/token/quality summary

## Benchmark Evidence

Latest generated artifacts are under:

```text
artifacts/agentic_runtime/
```

Key results:

```text
AWS CLI reference check:
  reference_found: 40/40
  output_section_found: 40/40
  reference_verified: 40/40

Offline full 40:
  quality_pass: 40/40
  aws_output_shape_recursive_pass: 40/40

Live full 40, max_output_tokens=80:
  provider_call_ok: 40/40
  aws_output_shape_recursive_pass: 40/40
  under_3s: 22/40
  under_4s: 37/40
  total_tokens: 10,907
  average latency: about 2.65s

Live full 40, max_output_tokens=40 experiment:
  provider_call_ok: 40/40
  aws_output_shape_recursive_pass: 40/40
  under_3s: 25/40
  under_4s: 38/40
  total_tokens: 9,307
  average latency: about 2.38s
```

The architecture passes AWS structure validation, but it does not yet make every command complete under 3 seconds.
The average latency is under 3 seconds, while the per-command p100 target is not met.

## Current Performance Bottleneck

The main remaining issue is tail latency from live model calls and some runtime overhead.

Observed patterns:

- some requests are dominated by OpenAI provider latency
- some requests have runtime overhead around service model loading, serialization, validation, and audit work
- reducing output tokens from 80 to 40 lowers total tokens and improves the number of under-3s commands, but does not solve all tail latency

The most likely next improvements are:

- deterministic fast paths for stable read/list operations
- caching service model and serializer setup more aggressively
- reducing live model calls when the deterministic plan is obvious
- keeping recursive shape validation in benchmark mode rather than always paying the cost in hot paths

## Design Tradeoff

This runtime prioritizes AWS response correctness and auditability over raw speed.

That tradeoff is intentional:

- plain LLM output can be faster to prototype but produces unreliable AWS structures
- deterministic rendering keeps shape correctness high
- live model calls still create tail latency, so p100 under 3 seconds needs more fast-path work

The current state is a good demonstration of a constrained single-agent runtime:

```text
agent decides intent and posture
runtime owns AWS correctness
validator proves the response shape
benchmark records live cost and latency
```
