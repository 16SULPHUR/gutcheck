# Questions and types

A question is a typed prompt about some text. There are three types, all inherited from Laya's interface.

| Type | Answers with | Example |
| --- | --- | --- |
| `choice` | One of N named options | Which department should handle this: billing, technical or sales? |
| `score` | A level on an ordered scale | How positive is this review, 1 to 5? |
| `noul` | Yes or no, as P(yes) | Does the customer ask for money back? |

For `score`, the order matters: predicting 4 when the truth is 5 is less wrong than predicting 1.

## Writing a good question

```json
{
  "type": "choice",
  "instructions": "Which department should handle this?",
  "criteria": {"billing": "invoices, refunds", "technical": "bugs, outages"}
}
```

- Phrase `instructions` as a plain question about the text.
- Use `criteria` to say what each option means. For `noul`, the keys are `"true"` and `"false"`.
- Keep options mutually exclusive. If two options can both be right, use two `noul` questions.

## The state

`state` is the thing being judged. It can be a string, a JSON object, or a list of chat turns. Multiple questions about one state are answered in a single request.

## What comes back

Each answer includes the type-specific result, `probabilities`, `confidence`, `answer_probability` and a `verdict`. See the [decide reference](/docs/reference/decide).
