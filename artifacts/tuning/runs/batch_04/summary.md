# Batch Summary

- scenarios: 5
- validation_passed: 5
- safe_fallback: 0
- missing_echo_total: 2
- placeholder_hits_total: 0
- llm_provider_failures: 5

| id | label | valid | fallback | missing_echo | placeholders |
| --- | --- | --- | --- | --- | --- |
| b04_s01 | logs describe-log-groups | True | False | - | - |
| b04_s02 | logs describe-log-streams | True | False | logGroupName | - |
| b04_s03 | cloudtrail lookup-events | True | False | - | - |
| b04_s04 | events list-rules | True | False | - | - |
| b04_s05 | events list-targets-by-rule | True | False | Rule | - |
