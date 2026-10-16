import boto3
from config import OPENSEARCH_INDEX, REGION, get_opensearch_host
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

host = get_opensearch_host().replace("https://", "").rstrip("/")
credentials = boto3.Session().get_credentials().get_frozen_credentials()
service = "aoss" if ".aoss.amazonaws.com" in host else "es"
auth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    service,
    session_token=credentials.token,
)
client = OpenSearch(
    hosts=[{"host": host, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)
print(f"documents index count: {client.count(index=OPENSEARCH_INDEX)['count']}")
