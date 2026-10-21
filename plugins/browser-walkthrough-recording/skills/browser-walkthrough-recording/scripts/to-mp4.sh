#!/usr/bin/env bash
# Encode a silent walkthrough without overwriting output or deleting the source.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo 'Usage: to-mp4.sh <input.webm> <new-output.mp4> (optional CRF=23)' >&2
  exit 2
fi
input="$1"
output="$2"
quality="${CRF:-23}"
[[ -f "$input" && "$input" == *.webm ]] || { echo 'Input must be an existing .webm file' >&2; exit 2; }
[[ "$output" == *.mp4 && ! -e "$output" && ! -L "$output" ]] || { echo 'Output must be a new .mp4 path' >&2; exit 2; }
[[ "$quality" =~ ^[0-9]+$ && "$quality" -ge 18 && "$quality" -le 28 ]] || { echo 'CRF must be an integer from 18 to 28' >&2; exit 2; }
command -v ffmpeg >/dev/null || { echo 'Missing ffmpeg: install FFmpeg with libx264 and add it to PATH.' >&2; exit 2; }
command -v ffprobe >/dev/null || { echo 'Missing ffprobe: install the FFmpeg tools and add ffprobe to PATH.' >&2; exit 2; }
# Encode beside the destination; failed conversions never leave a deliverable.
temporary_directory="$(mktemp -d "$(dirname "$output")/.walkthrough-encode.XXXXXX")"
trap 'rm -rf "$temporary_directory"' EXIT
encoded="$temporary_directory/video.mp4"
ffmpeg -nostdin -n -v error -i "$input" -map 0:v:0 -c:v libx264 -preset slow \
  -crf "$quality" -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -pix_fmt yuv420p \
  -movflags +faststart -an "$encoded"
ffmpeg -nostdin -v error -xerror -i "$encoded" -f null -
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height:format=duration,size -of json "$encoded"
# Hard-link publication is atomic and refuses an output created during encoding.
ln "$encoded" "$output"
printf 'Created %s; source retained for visual review.\n' "$output"
