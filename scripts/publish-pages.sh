#!/usr/bin/env bash
# Publish site/ (plus THESIS.md) to GitHub Pages (branch gh-pages). Run `make all` first.
set -euo pipefail
cd "$(dirname "$0")/.."
src=$(pwd); rev=$(git rev-parse --short HEAD); url=$(git remote get-url origin)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone -q -b gh-pages "$url" "$tmp"
cd "$tmp" && git rm -rq --ignore-unmatch . && cp "$src"/site/* . && cp "$src"/THESIS.md . && touch .nojekyll
git add -A && git commit -qm "site/ for Pages from main $rev" && git push -q origin gh-pages
echo "published $rev"
