#!/usr/bin/env bash
# Build the merged 1000-burst evaluation set (old eval cats 1-399 from the
# v80t080 'final' run + new cats 623-1224 from 'ext1000') as a directory of
# per-cat scenario_cos_theta_report.json copies, then aggregate it.
# Output names carry the cat count and date; existing outputs are never overwritten.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD=${OLD:-/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_final}
NEW=${NEW:-/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_ext1000}
MERGED=${MERGED:-/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_merged1000}
OLD_LAST=${OLD_LAST:-399}          # old eval cats; 400-621 are CT-v80 training cats

mkdir -p "$MERGED"
n_old=0; n_new=0
for d in "$OLD"/cat[0-9]*; do
    c=$(basename "$d"); n=$((10#${c#cat}))
    [ "$n" -le "$OLD_LAST" ] || continue
    [ -f "$d/scenario_cos_theta_report.json" ] || continue
    mkdir -p "$MERGED/$c"; cp -f "$d/scenario_cos_theta_report.json" "$MERGED/$c/"; n_old=$((n_old+1))
done
for d in "$NEW"/cat[0-9]*; do
    c=$(basename "$d")
    [ -f "$d/scenario_cos_theta_report.json" ] || continue
    mkdir -p "$MERGED/$c"; cp -f "$d/scenario_cos_theta_report.json" "$MERGED/$c/"; n_new=$((n_new+1))
done
n_tot=$((n_old+n_new))
tag="merged_${n_tot}cats_$(date +%Y%m%d)"
PDF="$MERGED/scenario_aggregate_v80_t080_${tag}.pdf"; JSON="$MERGED/scenario_aggregate_v80_t080_${tag}.json"
i=1; while [ -e "$PDF" ] || [ -e "$JSON" ]; do
    PDF="$MERGED/scenario_aggregate_v80_t080_${tag}_r$i.pdf"; JSON="$MERGED/scenario_aggregate_v80_t080_${tag}_r$i.json"; i=$((i+1))
done
echo "merged set: $n_old old (1-$OLD_LAST) + $n_new new = $n_tot cats in $MERGED"
cd "$REPO"
python3 python/ana/aggregate_scenario_reports.py --input-root "$MERGED" --output-pdf "$PDF" --output-json "$JSON"
echo "PDF:  $PDF"; echo "JSON: $JSON"
