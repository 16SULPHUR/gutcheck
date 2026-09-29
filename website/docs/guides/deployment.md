# Run in production

## Container

```bash
docker run -d -p 8080:8080 -v gutcheck-data:/data \
  -e GUTCHECK_API_KEY=change-me \
  -e GUTCHECK_STORE__SAVE_STATE=false \
  gutcheck
```

The `/data` volume holds cached model weights and the SQLite decision log. Keep it, or weights re-download on every start.

## Checklist

- **Set `api_key`.** Every endpoint except `/healthz` and the dashboard page then requires `Authorization: Bearer <key>`. The dashboard page loads without a key but its data calls need one.
- **Decide what to log.** `store.save_state: false` keeps decisions and probabilities but not the input text, which matters for sensitive data.
- **Pick a device.** CPU works but is slow (hundreds of milliseconds to seconds per request). A GPU brings it to tens of milliseconds. `engine.max_loaded: 2` fits 4 GB of VRAM.
- **Pre-load checkpoints.** `engine.models` are loaded at startup. Pack checkpoints load on first use, so send one warm-up request after a deploy.
- **Pin pack checkpoints** to a revision, which the bundled packs already do.

## Health and monitoring

- `GET /healthz` for liveness. It reports which checkpoints are loaded.
- Scrape `GET /metrics` with Prometheus. Alert on a rising share of `escalate` verdicts, which usually means input drift.
- Send feedback and run `/v1/calibrate` regularly so temperatures track real traffic.

## Scaling

Each instance owns its own SQLite log and learned temperatures. Run one instance per GPU, and treat feedback and calibration as per-instance until a shared store lands.
