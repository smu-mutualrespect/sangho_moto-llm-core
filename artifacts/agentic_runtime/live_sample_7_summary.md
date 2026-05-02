# Agentic Runtime Benchmark Summary

- Mode: live
- Seed: 1
- Sample size: 7
- Corpus size: 40
- Quality pass: 3/7
- Under 3s: 3/7
- Under 4s: 5/7
- Provider call OK: 7/7
- AWS output shape pass: 7/7
- AWS recursive shape pass: 7/7
- AWS CLI reference verified: 7/7
- Total tokens: 1914

| ID | Latency ms | <3s | <4s | Provider | AWS shape | Recursive | Ref | Quality | Tokens |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: |
| ec2_create_spot_datafeed_subscription | 4579.265 | False | False | True | True | True | True | False | 274 |
| iam_list_service_specific_credentials | 4304.851 | False | False | True | True | True | True | False | 275 |
| ec2_describe_reserved_instances_listings | 2496.7 | True | True | True | True | True | True | True | 262 |
| eks_list_addons | 2414.531 | True | True | True | True | True | True | True | 265 |
| ec2_modify_volume_attribute | 1615.731 | True | True | True | True | True | True | True | 290 |
| ecr_batch_check_layer_availability | 3237.739 | False | True | True | True | True | True | False | 291 |
| codeguru_reviewer_list_repository_associations | 3553.198 | False | True | True | True | True | True | False | 257 |
