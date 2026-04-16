# Batch Summary

- scenarios: 5
- validation_passed: 5
- safe_fallback: 0
- missing_echo_total: 4
- placeholder_hits_total: 0
- llm_provider_failures: 0

| id | label | valid | fallback | missing_echo | placeholders |
| --- | --- | --- | --- | --- | --- |
| b06_s01 | glue get-databases | True | False | MaxResults | - |
| b06_s02 | athena list-data-catalogs | True | False | MaxResults | - |
| b06_s03 | redshift-data list-databases | True | False | WorkgroupName | - |
| b06_s04 | lakeformation list-permissions | True | False | DataLakePrincipalIdentifier | - |
| b06_s05 | kms list-keys | True | False | - | - |
