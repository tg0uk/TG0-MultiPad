#!/usr/bin/env bash
set -euo pipefail

prefix="/tg0/multipad/raw_plot"
tags=()
dry_run=false
program_name="$(basename "$0")"

usage() {
  cat <<EOF
Usage: ${program_name} [--prefix TOPIC_PREFIX] [--tag TAG]... [--dry-run]

Open rqt_plot for TG0 multipad raw plot channels.

Options:
  --prefix TOPIC_PREFIX  Prefix that contains tag0..tagN topics.
                         Default: /tg0/multipad/raw_plot
  --tag TAG              Plot data1, data2, and data3 for one tag.
                         May be repeated. Default: 0.
  --dry-run              Print the rqt_plot command without launching the GUI.
  -h, --help             Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      prefix="${2:?--prefix requires a value}"
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --tag)
      tags+=("${2:?--tag requires a value}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

prefix="${prefix%/}"
if [ "${#tags[@]}" -eq 0 ]; then
  tags=(0)
fi

fields=()
for tag in "${tags[@]}"; do
  fields+=(
    "${prefix}/tag${tag}/data1/data"
    "${prefix}/tag${tag}/data2/data"
    "${prefix}/tag${tag}/data3/data"
  )
done
command=(ros2 run rqt_plot rqt_plot "${fields[@]}")

if [ "${dry_run}" = true ]; then
  printf '%s' "${command[0]}"
  for arg in "${command[@]:1}"; do
    printf ' %s' "${arg}"
  done
  printf '\n'
  exit 0
fi

exec "${command[@]}"
