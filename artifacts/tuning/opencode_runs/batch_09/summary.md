# Batch Summary

- scenarios: 5
- validation_passed: 5
- safe_fallback: 0
- missing_echo_total: 2
- placeholder_hits_total: 0
- llm_provider_failures: 0

| id | label | valid | fallback | missing_echo | placeholders |
| --- | --- | --- | --- | --- | --- |
| b09_s01 | codeartifact list-domains | True | False | - | - |
| b09_s02 | codeartifact list-repositories-in-domain | True | False | - | - |
| b09_s03 | codeartifact get-authorization-token | True | False | domain,domainOwner | - |
| b09_s04 | ssm list-documents | True | False | - | - |
| b09_s05 | resourcegroupstaggingapi get-tag-keys | True | False | - | - |
