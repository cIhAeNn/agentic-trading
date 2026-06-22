## Runtime Mode Configuration

Claude Desktop must inject runtime mode through `config/claude_desktop_config.json`.

Required production mode:

```json
"env": {
  "MODE": "PRODUCTION"
}
```

Recommended pattern-engine production settings:

```json
"env": {
  "MODE": "PRODUCTION",
  "PATTERN_MIN_CANDLES": "60",
  "PATTERN_LOOKBACK": "90",
  "PATTERN_MIN_RR": "1.50",
  "PATTERN_MAX_SETUPS": "3",
  "PATTERN_GLOBAL_VOLUME_OVERRIDE": "TRUE"
}
```

Accepted `MODE` values:

| Value        | Behavior                                               |
| ------------ | ------------------------------------------------------ |
| `PRODUCTION` | Compact runtime output, lowest token usage             |
| `PROD`       | Same as `PRODUCTION`                                   |
| `DEBUG`      | Full detector diagnostics and rejected-pattern reasons |

Use `MODE=PRODUCTION` for scheduled trading runs.
