"""Read-only V1 Meta transport subprocess oracle."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def main() -> int:
    source_path = Path(os.environ["V1_META_GRAPH_PATH"])
    spec = importlib.util.spec_from_file_location("v1_meta_graph_oracle", source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("v1_oracle_load_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    graph = module.MetaGraphClient(
        base_url=f"{os.environ['FAKE_META_ORIGIN']}/v26.0",
        access_token=os.environ["FIXTURE_PROVIDER_TOKEN"],
        max_retries=2,
        base_backoff_s=0,
    )
    profile = graph.get(
        "/page-1",
        params={"fields": "id,name,username,followers_count,fan_count"},
    )
    if os.getenv("PARITY_SCENARIO") == "retry":
        print(
            json.dumps(
                {"followers": profile.get("followers_count") or profile.get("fan_count") or 0},
                sort_keys=True,
            )
        )
        return 0
    rows = list(
        graph.paginated(
            "/page-1/published_posts",
            params={"fields": "id", "limit": 100},
        )
    )
    print(
        json.dumps(
            {
                "followers": profile.get("followers_count") or profile.get("fan_count") or 0,
                "content_ids": [row["id"] for row in rows],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
