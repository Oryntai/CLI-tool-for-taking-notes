# Demo Plan

Use this script to record a short terminal demo (30-60 seconds).

## Suggested Script

```bash
notes init
notes add "Draft architecture notes" --title "Design" --tags dev,ideas --pin
notes add "Prepare sprint summary" --tags work
notes list
notes search sprint
notes tags --all --limit 5
notes backup --out backup/notes.json.gz --compress
notes doctor
```

## Recording Tips

- Keep terminal width around 100-120 columns.
- Use a clean prompt and readable font.
- Type commands at a steady speed.
- Avoid exposing local paths or private data.
- Export as GIF for README or link asciinema recording.
