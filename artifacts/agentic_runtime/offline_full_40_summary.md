# Agentic Runtime Benchmark Summary

- Mode: offline_stub
- Seed: 1
- Sample size: 40
- Corpus size: 40
- Quality pass: 40/40
- Under 3s: 40/40
- Under 4s: 40/40
- Provider call OK: 40/40
- AWS output shape pass: 40/40
- AWS recursive shape pass: 40/40
- AWS CLI reference verified: 40/40
- Total tokens: 0

| ID | Latency ms | <3s | <4s | Provider | AWS shape | Recursive | Ref | Quality | Tokens |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: |
| bedrock_list_foundation_models | 1828.704 | True | True | True | True | True | True | True | 0 |
| ec2_monitor_instances | 1885.564 | True | True | True | True | True | True | True | 0 |
| ec2_unmonitor_instances | 8.904 | True | True | True | True | True | True | True | 0 |
| ec2_describe_reserved_instances | 6.351 | True | True | True | True | True | True | True | 0 |
| ec2_describe_reserved_instances_listings | 6.057 | True | True | True | True | True | True | True | 0 |
| ec2_purchase_reserved_instances_offering | 5.143 | True | True | True | True | True | True | True | 0 |
| ec2_describe_volume_status | 29.26 | True | True | True | True | True | True | True | 0 |
| ec2_modify_volume_attribute | 6.031 | True | True | True | True | True | True | True | 0 |
| ec2_create_spot_datafeed_subscription | 5.403 | True | True | True | True | True | True | True | 0 |
| ec2_describe_bundle_tasks | 7.412 | True | True | True | True | True | True | True | 0 |
| resource_explorer_list_indexes | 5.904 | True | True | True | True | True | True | True | 0 |
| resource_explorer_list_views | 7.967 | True | True | True | True | True | True | True | 0 |
| resource_explorer_search | 6.59 | True | True | True | True | True | True | True | 0 |
| support_describe_services | 7.444 | True | True | True | True | True | True | True | 0 |
| support_describe_trusted_advisor_check_result | 9.621 | True | True | True | True | True | True | True | 0 |
| support_describe_trusted_advisor_check_summaries | 7.321 | True | True | True | True | True | True | True | 0 |
| eks_list_addons | 7.329 | True | True | True | True | True | True | True | 0 |
| eks_describe_addon_versions | 6.985 | True | True | True | True | True | True | True | 0 |
| ssm_start_session | 6.687 | True | True | True | True | True | True | True | 0 |
| ecs_execute_command | 6.689 | True | True | True | True | True | True | True | 0 |
| billingconductor_list_billing_groups | 1982.968 | True | True | True | True | True | True | True | 0 |
| frauddetector_get_detectors | 1870.365 | True | True | True | True | True | True | True | 0 |
| detective_list_graphs | 1881.497 | True | True | True | True | True | True | True | 0 |
| auditmanager_list_assessments | 1892.336 | True | True | True | True | True | True | True | 0 |
| outposts_list_outposts | 1946.208 | True | True | True | True | True | True | True | 0 |
| appflow_list_flows | 2015.264 | True | True | True | True | True | True | True | 0 |
| omics_list_runs | 2168.53 | True | True | True | True | True | True | True | 0 |
| mgn_describe_source_servers | 1983.785 | True | True | True | True | True | True | True | 0 |
| codeguru_reviewer_list_repository_associations | 2104.947 | True | True | True | True | True | True | True | 0 |
| backup_gateway_list_gateways | 2043.895 | True | True | True | True | True | True | True | 0 |
| ssm_describe_instance_information | 10.193 | True | True | True | True | True | True | True | 0 |
| ecr_batch_check_layer_availability | 2018.833 | True | True | True | True | True | True | True | 0 |
| ecr_get_download_url_for_layer | 9.495 | True | True | True | True | True | True | True | 0 |
| ecr_initiate_layer_upload | 10.354 | True | True | True | True | True | True | True | 0 |
| ecr_complete_layer_upload | 9.427 | True | True | True | True | True | True | True | 0 |
| iam_get_context_keys_for_principal_policy | 2019.73 | True | True | True | True | True | True | True | 0 |
| iam_list_service_specific_credentials | 12.029 | True | True | True | True | True | True | True | 0 |
| iam_generate_service_last_accessed_details | 11.252 | True | True | True | True | True | True | True | 0 |
| secretsmanager_validate_resource_policy | 2016.734 | True | True | True | True | True | True | True | 0 |
| sts_decode_authorization_message | 1994.162 | True | True | True | True | True | True | True | 0 |
