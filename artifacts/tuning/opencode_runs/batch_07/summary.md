# Batch Summary

- scenarios: 5
- validation_passed: 4
- safe_fallback: 1
- missing_echo_total: 3
- placeholder_hits_total: 0
- llm_provider_failures: 0

| id | label | valid | fallback | missing_echo | placeholders |
| --- | --- | --- | --- | --- | --- |
| b07_s01 | organizations list-accounts | True | False | - | - |
| b07_s02 | organizations list-roots | True | False | - | - |
| b07_s03 | accessanalyzer list-findings | False | True | analyzerName,maxResults | - |
| b07_s04 | ram get-resource-shares | True | False | resourceOwner | - |
| b07_s05 | resourcegroupstaggingapi get-resources | True | False | - | - |
