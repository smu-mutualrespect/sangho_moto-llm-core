# Batch Summary

- scenarios: 5
- validation_passed: 5
- safe_fallback: 0
- missing_echo_total: 1
- placeholder_hits_total: 0
- llm_provider_failures: 0

| id | label | valid | fallback | missing_echo | placeholders |
| --- | --- | --- | --- | --- | --- |
| b02_s01 | ssm describe-instance-information | True | False | - | - |
| b02_s02 | ssm describe-automation-executions | True | False | MaxResults | - |
| b02_s03 | ssm get-inventory | True | False | - | - |
| b02_s04 | secretsmanager validate-resource-policy | True | False | - | - |
| b02_s05 | secretsmanager get-resource-policy | True | False | - | - |
