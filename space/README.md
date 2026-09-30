---
title: gutcheck live demo
emoji: ✅
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Live gutcheck gateway with the prompt-guard model
---

Public, locked-down gutcheck gateway that backs the demos on the gutcheck website.

Only `POST /v1/decide`, `GET /v1/packs` and `GET /healthz` are open. Inputs are capped, requests are rate limited per IP and nothing you type is stored.

Source: https://github.com/16SULPHUR/gutcheck (folder `space/`).
