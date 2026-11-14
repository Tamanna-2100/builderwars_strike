import hashlib
import json
import os
import re
from pathlib import Path

import boto3
from dotenv import load_dotenv


load_dotenv()


def ask(agent, system, user):
    model = os.environ[f"{agent.upper()}_MODEL_ID"]
    key = json.dumps([model, system, user], ensure_ascii=False, separators=(",", ":"))
    cache_path = Path(".cache") / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    if os.getenv("USE_CACHE_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise FileNotFoundError(f"No cached response for {agent}")

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))
    for attempt in range(2):
        response = client.converse(
            modelId=model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 4096},
        )
        text = "".join(block.get("text", "") for block in response["output"]["message"]["content"]).strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
        if fence:
            text = fence.group(1)
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            if attempt == 1:
                raise
            continue
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result