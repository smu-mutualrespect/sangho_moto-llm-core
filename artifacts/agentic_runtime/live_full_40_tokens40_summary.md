# Agentic Runtime Benchmark Summary

- Mode: live
- Seed: 1
- Sample size: 40
- Corpus size: 40
- Quality pass: 25/40
- Under 3s: 25/40
- Under 4s: 38/40
- Provider call OK: 40/40
- AWS output shape pass: 40/40
- AWS recursive shape pass: 40/40
- AWS CLI reference verified: 40/40
- Total tokens: 9307

| ID | Latency ms | <3s | <4s | Provider | AWS shape | Recursive | Ref | Quality | Tokens |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: |
| bedrock_list_foundation_models | 4352.001 | False | False | True | True | True | True | False | 214 |
| ec2_monitor_instances | 3068.67 | False | True | True | True | True | True | False | 232 |
| ec2_unmonitor_instances | 2095.607 | True | True | True | True | True | True | True | 234 |
| ec2_describe_reserved_instances | 1180.235 | True | True | True | True | True | True | True | 220 |
| ec2_describe_reserved_instances_listings | 1341.492 | True | True | True | True | True | True | True | 222 |
| ec2_purchase_reserved_instances_offering | 1166.797 | True | True | True | True | True | True | True | 261 |
| ec2_describe_volume_status | 2714.962 | True | True | True | True | True | True | True | 234 |
| ec2_modify_volume_attribute | 1181.687 | True | True | True | True | True | True | True | 250 |
| ec2_create_spot_datafeed_subscription | 1608.714 | True | True | True | True | True | True | True | 234 |
| ec2_describe_bundle_tasks | 2155.12 | True | True | True | True | True | True | True | 220 |
| resource_explorer_list_indexes | 1606.693 | True | True | True | True | True | True | True | 216 |
| resource_explorer_list_views | 1413.793 | True | True | True | True | True | True | True | 216 |
| resource_explorer_search | 1207.8 | True | True | True | True | True | True | True | 306 |
| support_describe_services | 1673.304 | True | True | True | True | True | True | True | 212 |
| support_describe_trusted_advisor_check_result | 1610.882 | True | True | True | True | True | True | True | 245 |
| support_describe_trusted_advisor_check_summaries | 1357.807 | True | True | True | True | True | True | True | 256 |
| eks_list_addons | 1061.236 | True | True | True | True | True | True | True | 225 |
| eks_describe_addon_versions | 1318.994 | True | True | True | True | True | True | True | 213 |
| ssm_start_session | 1155.556 | True | True | True | True | True | True | True | 223 |
| ecs_execute_command | 1764.792 | True | True | True | True | True | True | True | 244 |
| billingconductor_list_billing_groups | 3439.772 | False | True | True | True | True | True | False | 215 |
| frauddetector_get_detectors | 3106.898 | False | True | True | True | True | True | False | 216 |
| detective_list_graphs | 3810.183 | False | True | True | True | True | True | False | 213 |
| auditmanager_list_assessments | 2966.94 | True | True | True | True | True | True | True | 214 |
| outposts_list_outposts | 3444.108 | False | True | True | True | True | True | False | 214 |
| appflow_list_flows | 3556.209 | False | True | True | True | True | True | False | 213 |
| omics_list_runs | 3001.06 | False | True | True | True | True | True | False | 212 |
| mgn_describe_source_servers | 3214.256 | False | True | True | True | True | True | False | 213 |
| codeguru_reviewer_list_repository_associations | 3170.576 | False | True | True | True | True | True | False | 217 |
| backup_gateway_list_gateways | 5289.984 | False | False | True | True | True | True | False | 215 |
| ssm_describe_instance_information | 1613.662 | True | True | True | True | True | True | True | 229 |
| ecr_batch_check_layer_availability | 3221.634 | False | True | True | True | True | True | False | 251 |
| ecr_get_download_url_for_layer | 1251.735 | True | True | True | True | True | True | True | 241 |
| ecr_initiate_layer_upload | 1746.702 | True | True | True | True | True | True | True | 224 |
| ecr_complete_layer_upload | 1801.861 | True | True | True | True | True | True | True | 268 |
| iam_get_context_keys_for_principal_policy | 3704.812 | False | True | True | True | True | True | False | 263 |
| iam_list_service_specific_credentials | 2326.336 | True | True | True | True | True | True | True | 235 |
| iam_generate_service_last_accessed_details | 1753.396 | True | True | True | True | True | True | True | 259 |
| secretsmanager_validate_resource_policy | 3992.605 | False | True | True | True | True | True | False | 270 |
| sts_decode_authorization_message | 3762.607 | False | True | True | True | True | True | False | 248 |
