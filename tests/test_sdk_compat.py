"""A client written for TypeSafe's Jev works against gutcheck unchanged."""

import pytest

typesafe_sdk = pytest.importorskip("typesafe_sdk")


def test_typesafe_sdk_client(client, agents):
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

    agents["english"].probs["billing"] = 0.9
    sdk = TypeSafeClient(api_key="unused", base_url="http://testserver", http_client=client)
    r = sdk.system_one(
        state={"document": "I was charged twice. Please fix this ASAP."},
        questions={
            "billing": Noul(instructions="Is this ticket about billing?"),
            "tone": Choice(
                instructions="What is the customer's tone?",
                criteria={"calm": None, "frustrated": None, "angry": None},
            ),
            "urgency": Score(
                instructions="How urgent is this ticket?",
                criteria=["can wait", "this week", "today"],
            ),
        },
    )
    assert r.nouls["billing"].noul == 0.9
    assert r.choices["tone"].choice == "calm"
    assert r.scores["urgency"].score == pytest.approx(0.075)
    assert r.usage.input_tokens == 36
