# POST /v1/systemone

A drop-in for TypeSafe's Jev API and `laya-serve`. It takes the same request and returns Laya's answers unchanged, with no calibration, verdicts or packs.

Use it when you already have a client and only want to change its base URL:

```python
from typesafe_sdk import Noul, TypeSafeClient

client = TypeSafeClient(api_key="unused", base_url="http://localhost:8080")
client.system_one(
    state="I was charged twice", questions={"billing": Noul(instructions="Is this about billing?")}
)
```

| Field | Type | Notes |
| --- | --- | --- |
| `state` | string, object or list | What is being judged |
| `questions` | object | Name to typed question |
| `model` | string | Optional Laya checkpoint |

Requests here are also logged, and return `X-Gutcheck-Trace-Id`. For anything new, prefer [`/v1/decide`](/docs/reference/decide).
