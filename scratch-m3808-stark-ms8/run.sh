#!/bin/bash
S="$1"; cd "$(dirname "$S")"
for m in test_ms_header_1230 test_milestones_page test_milestones_dashboard test_milestones_crowded test_milestones_details test_milestones_calendar test_milestones_inline test_milestones_timeline_focus; do
  w=0
  while :; do
    l=$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)
    [ "$l" -lt 60 ] && break
    w=$((w+1)); [ $w -gt 25 ] && { echo "SKIPPED-LOAD $m" >> "$S/summary.txt"; continue 2; }
    sleep 60
  done
  echo "load1=$(cut -d' ' -f1 /proc/loadavg) start $m $(date +%T)" >> "$S/summary.txt"
  python3 dev/run_tests.py -j 1 $m > "$S/$m.out" 2>&1; echo "exit $? $m" >> "$S/summary.txt"
done
echo ALLDONE >> "$S/summary.txt"
