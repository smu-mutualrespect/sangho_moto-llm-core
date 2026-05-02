# Agentic Runtime Benchmark Summary

- Mode: live
- Seed: 1
- Sample size: 40
- Corpus size: 40
- Quality pass: 22/40
- Under 3s: 22/40
- Under 4s: 37/40
- Provider call OK: 40/40
- AWS output shape pass: 40/40
- AWS recursive shape pass: 40/40
- AWS CLI reference verified: 40/40
- Total tokens: 10907

| ID | Latency ms | <3s | <4s | Provider | AWS shape | Recursive | Ref | Quality | Tokens |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: |
| bedrock_list_foundation_models | 4249.759 | False | False | True | True | True | True | False | 254 |
| ec2_monitor_instances | 3601.85 | False | True | True | True | True | True | False | 272 |
| ec2_unmonitor_instances | 1533.212 | True | True | True | True | True | True | True | 274 |
| ec2_describe_reserved_instances | 3214.116 | False | True | True | True | True | True | False | 260 |
| ec2_describe_reserved_instances_listings | 2364.917 | True | True | True | True | True | True | True | 262 |
| ec2_purchase_reserved_instances_offering | 2525.531 | True | True | True | True | True | True | True | 301 |
| ec2_describe_volume_status | 3104.389 | False | True | True | True | True | True | False | 274 |
| ec2_modify_volume_attribute | 1740.757 | True | True | True | True | True | True | True | 290 |
| ec2_create_spot_datafeed_subscription | 1731.398 | True | True | True | True | True | True | True | 274 |
| ec2_describe_bundle_tasks | 2449.953 | True | True | True | True | True | True | True | 260 |
| resource_explorer_list_indexes | 1915.997 | True | True | True | True | True | True | True | 256 |
| resource_explorer_list_views | 1634.158 | True | True | True | True | True | True | True | 256 |
| resource_explorer_search | 2514.734 | True | True | True | True | True | True | True | 346 |
| support_describe_services | 2042.395 | True | True | True | True | True | True | True | 252 |
| support_describe_trusted_advisor_check_result | 1486.051 | True | True | True | True | True | True | True | 285 |
| support_describe_trusted_advisor_check_summaries | 1497.711 | True | True | True | True | True | True | True | 296 |
| eks_list_addons | 1475.132 | True | True | True | True | True | True | True | 265 |
| eks_describe_addon_versions | 1557.155 | True | True | True | True | True | True | True | 253 |
| ssm_start_session | 1472.177 | True | True | True | True | True | True | True | 263 |
| ecs_execute_command | 1582.021 | True | True | True | True | True | True | True | 284 |
| billingconductor_list_billing_groups | 3392.332 | False | True | True | True | True | True | False | 255 |
| frauddetector_get_detectors | 3644.341 | False | True | True | True | True | True | False | 256 |
| detective_list_graphs | 3370.504 | False | True | True | True | True | True | False | 253 |
| auditmanager_list_assessments | 3965.128 | False | True | True | True | True | True | False | 254 |
| outposts_list_outposts | 3259.228 | False | True | True | True | True | True | False | 254 |
| appflow_list_flows | 3770.978 | False | True | True | True | True | True | False | 253 |
| omics_list_runs | 3686.797 | False | True | True | True | True | True | False | 252 |
| mgn_describe_source_servers | 3846.87 | False | True | True | True | True | True | False | 253 |
| codeguru_reviewer_list_repository_associations | 3139.286 | False | True | True | True | True | True | False | 257 |
| backup_gateway_list_gateways | 3664.287 | False | True | True | True | True | True | False | 255 |
| ssm_describe_instance_information | 2099.807 | True | True | True | True | True | True | True | 269 |
| ecr_batch_check_layer_availability | 3268.06 | False | True | True | True | True | True | False | 291 |
| ecr_get_download_url_for_layer | 1426.795 | True | True | True | True | True | True | True | 281 |
| ecr_initiate_layer_upload | 1846.76 | True | True | True | True | True | True | True | 264 |
| ecr_complete_layer_upload | 1611.151 | True | True | True | True | True | True | True | 308 |
| iam_get_context_keys_for_principal_policy | 4027.804 | False | False | True | True | True | True | False | 303 |
| iam_list_service_specific_credentials | 1665.744 | True | True | True | True | True | True | True | 275 |
| iam_generate_service_last_accessed_details | 1776.638 | True | True | True | True | True | True | True | 299 |
| secretsmanager_validate_resource_policy | 3560.828 | False | True | True | True | True | True | False | 310 |
| sts_decode_authorization_message | 5280.574 | False | False | True | True | True | True | False | 288 |
