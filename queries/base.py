import os
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()


def get_client():
    """Create and return a ClickHouse client."""
    host = os.getenv("CLICKHOUSE_HOST", "http://localhost:8123")
    # Extract host and port from URL
    host_clean = host.replace("http://", "").replace("https://", "")
    if ":" in host_clean:
        host_part, port_part = host_clean.split(":")
        port = int(port_part)
    else:
        host_part = host_clean
        port = 8123

    return clickhouse_connect.get_client(
        host=host_part,
        port=port,
        database=os.getenv("CLICKHOUSE_DATABASE", "default"),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def execute_query(query: str) -> list[dict]:
    """Execute a query and return results as list of dicts."""
    client = get_client()
    result = client.query(query)
    columns = result.column_names
    rows = result.result_rows
    return [dict(zip(columns, row)) for row in rows]
