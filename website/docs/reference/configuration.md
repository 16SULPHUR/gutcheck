# Configuration

Settings come from, highest priority first: command-line flags, `GUTCHECK_*` environment variables, a YAML file (`--config` or `GUTCHECK_CONFIG`), then defaults. Nested keys use `__` in environment variables, for example `GUTCHECK_ENGINE__DEVICE=cuda`. Print the result with `gutcheck config`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `host` | `127.0.0.1` | Bind address (`0.0.0.0` in Docker) |
| `port` | `8080` | Bind port |
| `log_level` | `info` | `critical`, `error`, `warning`, `info` or `debug` |
| `engine.device` | auto | Torch device, for example `cpu` or `cuda` |
| `engine.models` | `[english, multilingual]` | Checkpoints loaded at startup. Others load on first use |
| `engine.max_loaded` | `2` | Checkpoints kept in memory. 2 fits 4 GB of VRAM |
| `api_key` | none | Require this bearer token on the API |
| `policy.act_at` | `0.9` | Minimum answer probability for `act` |
| `policy.review_at` | `0.6` | Minimum answer probability for `review` |
| `store.path` | `gutcheck.db` | SQLite decision log. `null` disables it |
| `store.save_state` | `true` | Keep the input text in the log |
| `packs.dirs` | `[]` | Extra directories to load packs from |
| `calibration.min_samples` | `30` | Labels needed before feedback recalibrates a question |

## Example

```yaml
host: 0.0.0.0
port: 8080
api_key: change-me
engine:
  device: cuda
  models: [english, multilingual]
  max_loaded: 2
policy:
  act_at: 0.9
  review_at: 0.6
store:
  path: /data/gutcheck.db
  save_state: false
packs:
  dirs: [/packs]
calibration:
  min_samples: 30
```
