import time
import uuid

def get_current_aws_time() -> str:
    # AWS에서 주로 사용하는 날짜 형식 반환
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def generate_fake_request_id() -> str:
    # AmznRequestId와 같은 형식의 UUID 생성
    return str(uuid.uuid4())

def generate_fake_arn(service: str, resource_type: str, account_id: str = "123456789012") -> str:
    # 실제와 유사한 ARN 생성기
    return f"arn:aws:{service}:::{account_id}:{resource_type}/{str(uuid.uuid4())[:8]}"
