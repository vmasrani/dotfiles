#!/usr/bin/env zsh
# Table preview via DuckDB for csv / tsv / parquet / jsonl / sqlite+duckdb files.
#
#   summary line : rows · columns · size (+ row groups and writer for parquet)
#   sample       : row-wise table; flips to one-line-per-column when the table
#                  is too wide for the pane to show every column
#   column stats : type, min, max, distinct, mean, null % (DuckDB SUMMARIZE)
#                  over the whole file, or the first 100,000 rows past 1 GB
#
# Malformed files fail loudly with DuckDB's own error instead of dropping rows.
set -euo pipefail

(( $# == 1 )) || { print -u2 "usage: table-preview <file>"; exit 2; }
command -v duckdb >/dev/null || { print -u2 "table-preview: duckdb not found (run setup.sh or 'brew install duckdb')"; exit 1; }
[[ -f $1 ]] || { print -u2 "table-preview: no such file: $1"; exit 1; }

file=$1
q=${file//\'/\'\'}
width=${FZF_PREVIEW_COLUMNS:-$(tput cols 2>/dev/null || print 120)}
height=${FZF_PREVIEW_LINES:-40}
bytes=$(( $(wc -c <"$file") ))
big_limit=$(( 1024 ** 3 ))
stats_rows=100000

pre=()         # statements every duckdb call needs first (e.g. ATTACH)
extra=()       # extra SQL expressions for the summary line
rows_sql=""    # SQL for the row count; empty = count from the stats
case ${file:l} in
  *.csv)           src="read_csv('$q', delim=',')" ;;
  *.tsv|*.tab)     src="read_csv('$q', delim='\t')" ;;
  *.jsonl|*.ndjson) src="read_json('$q', format='newline_delimited')" ;;
  *.parquet)
    src="read_parquet('$q')"
    meta="(FROM parquet_file_metadata('$q'))"
    rows_sql="(SELECT num_rows FROM $meta)"
    extra=(
      "plural((SELECT num_row_groups FROM $meta), 'row group')"
      "coalesce((SELECT regexp_replace(created_by, ' version| \(build.*\)', '', 'g') FROM $meta), 'unknown writer')"
    )
    ;;
  *.db|*.sqlite|*.sqlite3|*.duckdb)
    pre=(-c "ATTACH '$q' AS db (READ_ONLY)")
    tables=$(duckdb "${pre[@]}" -list -noheader -c "
      SELECT string_agg(table_name, ' ' ORDER BY table_name)
      FROM duckdb_tables() WHERE database_name = 'db'")
    [[ -n $tables ]] || { print "[database has no tables]"; exit 0; }
    first=${tables%% *}
    src="db.\"${first//\"/\"\"}\""
    extra=("'showing table $first (tables: ${${tables// /, }//\'/\'\'})'")
    ;;
  *) print -u2 "table-preview: unsupported file type: $file"; exit 1 ;;
esac

if (( bytes > big_limit )); then
  stats_src="(FROM $src LIMIT $stats_rows)"
  stats_title="column stats · first $(duckdb -list -noheader -c "SELECT format('{:,}', $stats_rows)") rows (file over 1 GB)"
  [[ -n $rows_sql ]] || rows_sql="NULL"
else
  stats_src=$src
  stats_title="column stats · whole file"
fi
rows_expr="coalesce(plural(${rows_sql:-(SELECT max(count) FROM s)}, 'row'), 'rows not counted (file over 1 GB)')"
summary_sql="SELECT concat_ws(' · ', $rows_expr,
  plural((SELECT count(*) FROM s), 'column'),
  format_bytes($bytes)${extra:+, }${(j:, :)extra})"

stats_sql="SELECT column_name AS \"column\",
  lower(column_type) AS type,
  left(min, 24) AS min,
  left(max, 24) AS max,
  approx_unique AS \"distinct\",
  coalesce(printf('%.4g', try_cast(avg AS DOUBLE)), '') AS mean,
  null_percentage || '%' AS \"null %\"
FROM s"

# One process: summarise once, print the summary line, then the stats table.
stats_out=$(duckdb "${pre[@]}" \
  -c "CREATE MACRO plural(n, word) AS format('{:,} ', n) || word || CASE WHEN n = 1 THEN '' ELSE 's' END" \
  -c "CREATE TEMP TABLE s AS FROM (SUMMARIZE FROM $stats_src)" \
  -list -noheader -c "$summary_sql" \
  -c ".mode duckbox" -c ".headers on" -c ".highlight_results on" \
  -c ".maxwidth $width" -c ".maxrows 1000" -c "$stats_sql")

sample_rows=$(( height / 2 - 6 ))
(( sample_rows < 5 )) && sample_rows=5
(( sample_rows > 20 )) && sample_rows=20

ddb() { duckdb "${pre[@]}" -c ".highlight_results on" -c ".maxwidth $width" "$@"; }
rows_view()    { ddb -c ".maxrows $sample_rows" -c "FROM $src LIMIT $sample_rows"; }
columns_view() { ddb -c ".maxrows 1000" -c ".columns" -c "FROM $src LIMIT 5"; }

dim=$'\e[90m' magenta=$'\e[35m' reset=$'\e[0m'
print -r -- "$magenta${stats_out%%$'\n'*}$reset"
print

sample=$(rows_view)
if [[ $sample == *" columns ("*" shown)"* ]]; then
  columns_view
else
  print -r -- "$sample"
fi

print -r -- "$dim$stats_title$reset"
print -r -- "${stats_out#*$'\n'}"
