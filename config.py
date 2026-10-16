import os
from functools import lru_cache

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "documents")


@lru_cache(maxsize=1)
def get_opensearch_host() -> str:
    value = os.getenv("OPENSEARCH_ENDPOINT") or os.getenv("OPENSEARCH_DOMAIN")
    if not value:
        raise RuntimeError("Set OPENSEARCH_ENDPOINT or OPENSEARCH_DOMAIN")

    value = value.replace("https://", "").rstrip("/")
    if ".amazonaws.com" in value:
        return value

    status = boto3.client("opensearch", region_name=REGION).describe_domain(
        DomainName=value
    )["DomainStatus"]

    endpoint = status.get("Endpoint") or (status.get("Endpoints") or {}).get("vpc")
    if not endpoint:
        raise RuntimeError(f"No endpoint found for OpenSearch domain: {value}")
    return endpoint
