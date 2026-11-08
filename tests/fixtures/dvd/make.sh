#!/usr/bin/env -S nix shell nixpkgs#bash nixpkgs#ffmpeg nixpkgs#dvdauthor nixpkgs#cdrkit --command bash
# Regenerates this directory's synthetic DVD: three titles in two title sets,
# made from test patterns. Only the IFO and BUP files are kept, which is all
# lsdvd reads, and the ISO is built from those alone.
set -euo pipefail
cd "$(dirname "$0")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

for title in 1:20 2:45 3:8; do
  n="${title%%:*}"
  seconds="${title##*:}"
  ffmpeg -v error -f lavfi -i "testsrc=d=$seconds:s=720x480:r=30000/1001" \
    -f lavfi -i "sine=f=$((300 + n * 100)):d=$seconds" \
    -target ntsc-dvd -b:v 400k "$work/t$n.mpg"
done

cat >"$work/dvd.xml" <<EOF
<dvdauthor>
  <vmgm />
  <titleset>
    <titles>
      <pgc><vob file="$work/t1.mpg" chapters="0,5,10,15" /></pgc>
      <pgc><vob file="$work/t2.mpg" chapters="0,10,20,30,40" /></pgc>
    </titles>
  </titleset>
  <titleset>
    <titles>
      <pgc><vob file="$work/t3.mpg" chapters="0" /></pgc>
    </titles>
  </titleset>
</dvdauthor>
EOF
VIDEO_FORMAT=NTSC dvdauthor -o "$work/dvd" -x "$work/dvd.xml" 2>/dev/null

mkdir -p "$work/ifo/VIDEO_TS"
cp "$work"/dvd/VIDEO_TS/*.IFO "$work"/dvd/VIDEO_TS/*.BUP "$work/ifo/VIDEO_TS/"
rm -rf VIDEO_TS synthetic.iso
cp -r "$work/ifo/VIDEO_TS" .
genisoimage -quiet -dvd-video -V SYNTHETIC_DVD -o synthetic.iso "$work/ifo"
