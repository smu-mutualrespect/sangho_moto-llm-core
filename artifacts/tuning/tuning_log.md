# Tuning Log

## Pass 0

Status: planned

- Objective:
  - establish a 50-command fallback corpus
  - run in 10 batches of 5
  - record shortcomings and tune only generic behavior

- Initial known weak points:
  - placeholder-like scalar values in generic string fields
  - inconsistent identifier variation rules for strict IDs
  - limited request-aware echo behavior
  - shallow world-state consistency beyond a few resource types

## Pass 1

Status: completed

- What I ran:
  - built a 50-command corpus in `artifacts/tuning/command_corpus.json`
  - grouped into 10 batches of 5
  - added `scripts/run_honeypot_tuning_batches.py`
  - executed batches against the current generic fallback pipeline

- Findings:
  - all executed scenarios serialized and validated, but some corpus entries used service models that hung in this environment
  - runner stopped the whole batch on one bad scenario instead of recording the exception and continuing
  - first-cut metrics overstated `missing_echo` because some input identifiers do not naturally appear in the output shape
  - placeholder artifacts were visible in generic strings
    - `ServiceCredentialAlias`
    - `IPAddress`
    - `IamRole`
    - synthetic SSM instance `Name`

- Changes made:
  - replaced unstable late-batch services with stable service/model combinations
  - made the batch runner resilient to per-scenario exceptions
  - kept summaries in `artifacts/tuning/runs/batch_*/summary.{json,md}`

## Pass 2

Status: completed

- What felt weak:
  - generic scalar generation still leaked obvious placeholders
  - plural request identifiers such as `layerDigests` were not reused when output used singular fields like `layerDigest`
  - string variation rules accidentally corrupted strict IDs or semantic names

- Generic fixes applied:
  - `moto/core/llm_agents/normalizer.py`
    - add singular aliases when extracting target identifiers from plural list inputs
  - `moto/core/llm_agents/shape_adapter.py`
    - add concrete rules for:
      - `IPAddress`
      - `IamRole`
      - `DetailedStatus`
      - `AssociationStatus`
      - `ServiceCredentialAlias`
      - `Region`
      - `ResourceType`
      - backup cron/timezone/status message fields
      - `mediaType`
      - `Name` fields using attacker input when plausible
    - stop varying strict identifiers and semantic names too aggressively

- Result after rerun:
  - placeholder hits in the affected batches dropped to zero
  - ECR digest echo improved because plural request input now maps into singular output members

## Pass 3

Status: completed

- What felt weak:
  - evaluation still marked some scenarios as bad even when the output shape would not normally echo the input
  - examples:
    - `GetAccessKeyLastUsed` does not need to echo `AccessKeyId`
    - `ValidateResourcePolicy` does not need to echo `SecretId`
    - `GetDetector` does not need to echo `detectorId`

- Changes made:
  - refined `expected_echo` in the corpus to match plausible output-shape behavior
  - tightened placeholder heuristics in the runner so that real placeholders are caught, but substrings like `IamRoleArn` do not trigger false positives

- Current aggregate after reruns:
  - 50 scenarios recorded
  - 50 validation passes
  - 0 safe fallbacks
  - 0 placeholder hits in rerun-targeted batches
  - 11 remaining `missing_echo` counts, mostly from outputs where echo behavior is arguable rather than clearly wrong

## Remaining Gaps

- No external LLM provider was active during this run:
  - every scenario shows `provider_call_failed`
  - tuning therefore exercised the deterministic fallback and generic shaping path, not a live model-backed planner

- Still weak:
  - world-state continuity across unrelated batches is shallow
  - some modern or heavy service models are too slow to use in this local tuning corpus
  - response semantics are shape-correct and plausible, but not yet deeply persona-driven

## Pass 4

Status: completed

- Trigger:
  - live `opencode` probes were enabled and exposed two quality issues that deterministic fallback had hidden
  - `ecr:GetDownloadUrlForLayer` produced a realistic public `https://...` URL, which the safety validator correctly rejected
  - `ssm:DescribeInstanceInformation` returned `InstanceInformationList: []`, which is schema-valid but weak for a honeypot

- Changes made:
  - `moto/core/llm_agents/response_plan.py`
    - sanitize `downloadUrl` hints from public HTTP(S) into internal decoy `mock://ecr/...` URLs before rendering
    - normalize `DescribeInstanceInformation` plans so `instance_count` is at least 1
    - drop explicit empty `InstanceInformationList` hints for that operation
  - `moto/core/llm_agents/shape_adapter.py`
    - ignore explicit empty `InstanceInformationList` lists for SSM describe
    - honor `instance_count` when generating that list and clamp it to `1..3`
  - `moto/core/llm_agents/providers.py`
    - add `MOTO_LLM_OPENCODE_TIMEOUT` override and raise the default OpenCode subprocess budget to 30 seconds
    - this prevents slower but valid query-protocol probes from dropping into fallback just because the model exceeded the old 20 second cap

- Expected outcome:
  - live model-backed ECR download responses should pass safety validation without degrading to generic AccessDenied fallback
  - live model-backed SSM describe responses should keep at least one decoy managed instance in reconnaissance flows

## Pass 5

Status: completed

- Trigger:
  - ran the full 50-scenario corpus through live `opencode` in 10 batches with `.env` credentials and `MOTO_LLM_OPENCODE_TIMEOUT=35`
  - goal was to verify real model-backed behavior rather than deterministic fallback behavior

- Aggregate result:
  - 50 scenarios executed
  - 47 validation passes
  - 1 safe fallback
  - 0 `provider_call_failed`
  - 0 placeholder hits
  - 19 `missing_echo` counts, mostly from arguable expectations rather than protocol failures

- Concrete weak spots observed:
  - `ecr:DescribeImages`
    - model emitted a natural-language timestamp hint (`"recent"`) that later broke timestamp serialization
  - `eks:DescribeCluster`
    - model emitted another natural-language timestamp hint (`"recent-ish but established"`) with the same failure mode
  - `accessanalyzer:ListFindings`
    - response rendered with an ARN carrying the wrong account id, which tripped world-state validation and degraded to safe fallback
  - several list/describe APIs still return semantically thin but schema-valid values:
    - generic names like `CatalogName`
    - weak pagination or resource-owner echo behavior

- Tuning conclusion:
  - live `opencode` connectivity is now stable enough for iterative tuning
  - the next fixes should target:
    - timestamp-hint sanitization before shape serialization
    - stronger account-id normalization for generated ARNs and IDs
    - richer request-aware echoes for list APIs where attacker-supplied context should plausibly reappear

## Pass 6

Status: completed

- Trigger:
  - pass 5 exposed three concrete model-backed failures:
    - natural-language timestamp hints like `recent`
    - wrong account ids inside explicit ARN hints
    - type mismatches inside nested explicit hints, especially map fields such as `principal`

- Changes made:
  - `moto/core/llm_agents/shape_adapter.py`
    - coerce explicit hints through the target shape before rendering
    - normalize timestamp hints into ISO or numeric values
    - rewrite explicit ARN strings to the locked account id and region
    - collapse scalar shape mismatches:
      - `string` fields now stringify dict/list hints safely
      - `boolean`/`integer`/`float` fields now coerce mismatched explicit values instead of crashing

- Result after targeted reruns:
  - `batch_3`: now 5/5 validation pass
  - `batch_5`: now 5/5 validation pass
  - `batch_7`: now 5/5 validation pass, no fallback, no runner exception
  - remaining imperfections are now mostly semantic thinness or missing echo, not protocol/runtime breakage
