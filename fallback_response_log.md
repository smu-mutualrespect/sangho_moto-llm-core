# Moto LLM Fallback Response Log

| Timestamp (KST) | Command | Handler | Exit | Response |
|---|---|---:|---:|---|
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc` | LLM fallback via OpenCode | 0 | `{"layers":[],"failures":[{"layerDigest":"sha256:abc","failureCode":"InvalidLayerDigest","failureReason":"Layer digest must be a valid sha256 value."}]}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc` | LLM fallback via OpenCode | 0 | `{"downloadUrl":"https://ecr-fallback.local/v2/demo/blobs/sha256:abc?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=test%2F20260411%2Fus-east-1%2Fecr%2Faws4_request&X-Amz-Date=20260411T110822Z&X-Amz-Expires=300&X-Amz-SignedHeaders=host&X-Amz-Signature=0000000000000000000000000000000000000000000000000000000000000000","layerDigest":"sha256:abc"}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo` | LLM fallback via OpenCode | 0 | `{"uploadId":"hpot-upload-7f3c2a9b4e6d1f08","partSize":20971520}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc` | LLM fallback via OpenCode | 0 | `{"repositoryName":"demo","uploadId":"test","layerDigest":"sha256:abc"}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 iam create-user --user-name victim-admin-3` | Moto native | 0 | `{"User":{"Path":"/","UserName":"victim-admin-3","UserId":"rts39r6q24xvi0pl81p7","Arn":"arn:aws:iam::123456789012:user/victim-admin-3","CreateDate":"2026-04-11T11:09:02.249493+00:00"}}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 iam create-access-key --user-name victim-admin-3` | Moto native | 0 | `{"AccessKey":{"UserName":"victim-admin-3","AccessKeyId":"REDACTED_FAKE_ACCESS_KEY_ID","Status":"Active","SecretAccessKey":"REDACTED_FAKE_SECRET_ACCESS_KEY","CreateDate":"2026-04-11T11:09:02.783291+00:00"}}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 iam attach-user-policy --user-name victim-admin-3 --policy-arn arn:aws:iam::aws:policy/AdministratorAccess` | Moto native error | 254 | `An error occurred (NoSuchEntity) when calling the AttachUserPolicy operation: Policy arn:aws:iam::aws:policy/AdministratorAccess does not exist or is not attachable.` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 sts get-caller-identity` | Moto native | 0 | `{"UserId":"REDACTED_FAKE_USER_ID","Account":"123456789012","Arn":"arn:aws:sts::123456789012:user/moto"}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager list-secrets` | Moto native | 0 | `{"SecretList":[]}` |
| 2026-04-11 20:09 | `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information` | LLM fallback via OpenCode | 0 | `{"InstanceInformationList":[]}` |
| 2026-04-11 21:13 | `aws --endpoint-url=http://127.0.0.1:5001 iam create-service-specific-credential --user-name victim-admin --service-name codecommit.amazonaws.com` | LLM fallback via OpenCode | 0 | `{"ServiceSpecificCredential":{"CreateDate":"2026-04-11T12:13:03+00:00","ServiceName":"codecommit.amazonaws.com","ServiceUserName":"test-at-20260411T121303Z","ServicePassword":"moto-fallback-password-6f3b9a2c","ServiceSpecificCredentialId":"ACCAEXAMPLEFALLBACK123","UserName":"test","Status":"Active"}}` |
| 2026-04-11 21:13 | `aws --endpoint-url=http://127.0.0.1:5001 iam simulate-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin --action-names iam:AttachUserPolicy secretsmanager:GetSecretValue sts:AssumeRole` | fallback failure | 255 | `Unable to parse response; invalid XML received: {"message":"llm_fallback!!"}` |
| 2026-04-11 21:14 | `aws --endpoint-url=http://127.0.0.1:5001 iam generate-service-last-accessed-details --arn arn:aws:iam::123456789012:user/victim-admin` | fallback failure | 255 | `Unable to parse response; invalid XML received: {"message":"llm_fallback!!"}` |
| 2026-04-11 21:14 | `aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=` | LLM fallback via OpenCode | 0 | `{"DecodedMessage":"{\"allowed\":false,\"decoded\":\"Moto fallback honeypot response\",\"context\":{\"service\":\"sts\",\"action\":\"DecodeAuthorizationMessage\"}}"}` |
| 2026-04-11 21:14 | `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'` | LLM fallback via OpenCode | 0 | `{"PolicyValidationPassed":false,"ValidationErrors":[{"CheckName":"SECURITY_WARNING","ErrorMessage":"This resource policy allows broad access because the principal is set to '*' and the resource is set to '*'."}]}` |
| 2026-04-11 21:15 | `aws --endpoint-url=http://127.0.0.1:5001 iam list-service-specific-credentials --user-name victim-admin` | fallback parse failure | 255 | `'ListServiceSpecificCredentialsResult'` |
| 2026-04-11 21:15 | `aws --endpoint-url=http://127.0.0.1:5001 iam reset-service-specific-credential --user-name victim-admin --service-specific-credential-id ACCAEXAMPLEFALLBACK123` | fallback failure | 255 | `Unable to parse response; invalid XML received: {"message":"llm_fallback!!"}` |
| 2026-04-11 21:15 | `aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin` | LLM fallback via OpenCode | 0 | `{"ContextKeyNames":[]}` |

## Latency Run

| Timestamp (KST) | Command | Handler | Exit | CLI elapsed ms | LLM elapsed ms | Result |
|---|---|---:|---:|---:|---:|---|
| 2026-04-11 21:48 | `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc` | LLM fallback via OpenCode | 0 | 15175 | 13624 | Parsed JSON response |
| 2026-04-11 21:49 | `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc` | LLM fallback via OpenCode | 0 | 14250 | 13432 | Parsed JSON response |
| 2026-04-11 21:49 | `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo` | LLM fallback via OpenCode | 0 | 16927 | 16135 | Parsed JSON response |
| 2026-04-11 21:49 | `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc` | LLM fallback via OpenCode | 0 | 13473 | 12667 | Parsed JSON response |
| 2026-04-11 21:49 | `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information` | LLM fallback via OpenCode | 0 | 17696 | 14559 | Parsed JSON response |
| 2026-04-11 21:50 | `aws --endpoint-url=http://127.0.0.1:5001 iam create-service-specific-credential --user-name victim-admin --service-name codecommit.amazonaws.com` | fallback failure | 255 | 24882 | n/a | `{"message":"llm_fallback!!"}` caused IAM XML parse failure |
| 2026-04-11 21:50 | `aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin` | LLM fallback via OpenCode | 0 | 20041 | 19399 | Parsed JSON response |
| 2026-04-11 21:51 | `aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=` | fallback parse failure | 255 | 23402 | 17538 | LLM returned JSON, but AWS CLI expected XML in this path |
| 2026-04-11 21:51 | `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'` | LLM fallback via OpenCode | 0 | 19577 | 18534 | Parsed JSON response |

## Latency Run: Direct API gpt-5.4-nano

| Timestamp (KST) | Command | Handler | Exit | CLI elapsed ms | LLM elapsed ms | Result |
|---|---|---:|---:|---:|---:|---|
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 3855 | 2119 | Parsed JSON response |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 2243 | 1468 | Parsed JSON response |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 4902 | 4125 | Parsed JSON response |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 2121 | 1338 | Parsed JSON response |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 3965 | 877 | Parsed JSON response |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 iam create-service-specific-credential --user-name victim-admin --service-name codecommit.amazonaws.com` | fallback parse failure via direct API `gpt-5.4-nano` | 255 | 6591 | 1441 | JSON response caused IAM XML parse failure; credential-looking values redacted |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin` | fallback parse failure via direct API `gpt-5.4-nano` | 255 | 2006 | 1308 | JSON response caused IAM XML parse failure |
| 2026-04-11 22:02 | `aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=` | fallback parse failure via direct API `gpt-5.4-nano` | 255 | 6011 | 1784 | JSON response caused XML parse failure |
| 2026-04-11 22:03 | `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'` | LLM fallback via direct API `gpt-5.4-nano` | 0 | 1952 | 1256 | Parsed JSON response, but lower quality: empty validation error objects |

### Comparison: OpenCode vs Direct API gpt-5.4-nano

| Scope | OpenCode avg CLI ms | API nano avg CLI ms | OpenCode avg LLM ms | API nano avg LLM ms | Quality note |
|---|---:|---:|---:|---:|---|
| All 9 README fallback commands | 18380 | 4183 | n/a | 1746 | API nano was much faster, but 3/9 commands failed parsing vs 2/9 for OpenCode in the prior run. |
| ECR 4 commands + SSM command | 15504 | 3417 | 14083 | 1985 | API nano was about 4.5x faster end-to-end and about 7.1x faster in LLM call time for the most stable command set. |
