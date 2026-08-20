#!/usr/bin/env zsh
#
# Stop hook: warns when the last assistant message doesn't start with the
# bolded canary word (see global CLAUDE.md "Canary" section). Silent in
# every other case -- including malformed/absent transcript data -- since
# this is a warning, never a gate.

transcript_path=$(jq -r '.transcript_path // empty' 2>/dev/null)

[[ -z "$transcript_path" || "$transcript_path" == "null" || ! -f "$transcript_path" ]] && exit 0

# Transcript is JSONL, one JSON record per line. Assistant records have
# .type == "assistant" with .message.content as an array of blocks (text,
# tool_use, ...). Slurp just the tail into one array so a single jq call
# can flatten every text block from every assistant record IN ORDER and
# take the last one -- this is the last assistant message's last text
# block, robust to tool_use blocks before/after it and to multi-line text.
last_text=$(tail -n 50 "$transcript_path" | jq -rs '
  [ .[] | select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text ]
  | if length > 0 then last else empty end
' 2>/dev/null)

[[ -z "$last_text" ]] && exit 0

trimmed=$(printf '%s' "$last_text" | sed -e 's/^[[:space:]]*//')

# NOTE: the pattern must live in a variable -- zsh's =~ fails to compile an
# inline "\*\*" literal ("repetition-operator operand invalid").
bold_pattern='^\*\*[[:alnum:]]'
[[ "$trimmed" =~ $bold_pattern ]] && exit 0

printf '%s\n' '{"systemMessage":"⚠ canary absent — first word not bolded; possible context rot"}'
exit 0
