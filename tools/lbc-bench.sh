#!/bin/sh
# lbc-bench.sh - SHORT runtime benchmark for the LubanCat-3 AMP board.
# Kept under ~40 s because the board has no heatsink (long CPU load would
# throttle and pollute the comparison).
#
#   ssh root@192.168.77.2 'sh -s' < tools/lbc-bench.sh [label]
#
# Reports Min/Act/Avg/Max for cyclictest (idle + cpu-load), a stress-ng
# throughput line, and hackbench, plus thermal before/after.
# NOTE: oslat is not usable in this image (libnuma missing) - skipped.

label="${1:-$(uname -r)}"
CY=/usr/bin/cyclictest
CPUC=4    # cyclictest affinity, idle phase
CPUL=7    # cyclictest affinity, load phase
N=10000   # 10000 x 1ms = 10 s per cyclictest run

therm() {
	for z in /sys/class/thermal/thermal_zone*/temp; do
		printf '%s ' "$(cat "$z" 2>/dev/null)"
	done
	printf 'freq=%s' "$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq 2>/dev/null)"
}
# No heatsink: wait (up to ~150 s) until the hottest zone is <= 48 C so every
# variant starts from a comparable thermal state.
maxtemp() {
	m=0
	for z in /sys/class/thermal/thermal_zone*/temp; do
		t=$(cat "$z" 2>/dev/null)
		[ -n "$t" ] && [ "$t" -gt "$m" ] && m=$t
	done
	echo "$m"
}
wait_cool() {
	i=0
	while [ "$(maxtemp)" -gt 48000 ] && [ "$i" -lt 30 ]; do
		sleep 5; i=$((i+1))
	done
	echo "  (cool wait ${i}x5s, now max=$(maxtemp))"
}
cyclic() { # $1=tag $2=cpu
	"$CY" -m -p99 -i1000 -l "$N" -t1 -a "$2" -q 2>&1 \
		| grep '^T:' | sed "s/^/  [$1] /"
}

echo "==================== lbc-bench: $label ===================="
echo "[env] $(date '+%F %T') uptime=$(cut -d. -f1 /proc/uptime)s  kernel=$(uname -r)"
echo "[env] cc=$(zcat /proc/config.gz 2>/dev/null | sed -n 's/^CONFIG_CC_VERSION_TEXT="\(.*\)"/\1/p')"
echo "[env] lto=$(zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_LTO_' | tr '\n' ' ')"
echo "[env] governor=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null)  nproc=$(nproc)"
wait_cool
echo "[th ] before: $(therm)"

echo "---- phase A: idle (10s) ----"
cyclic idle "$CPUC"

echo "---- phase B: cpu-load = stress-ng --cpu 6 (10s) ----"
stress-ng --cpu 6 --timeout 14s --quiet >/dev/null 2>&1 &
sleep 2
cyclic cpuload "$CPUL"
wait 2>/dev/null

echo "---- phase C: throughput = stress-ng --cpu 8 (5s) ----"
stress-ng --cpu 8 --cpu-method matrixprod --timeout 5s --metrics-brief 2>&1 \
	| grep -E 'stress-ng: metrc' | tail -3 | sed 's/^/  /'

echo "---- phase D: scheduler = hackbench ----"
hackbench -s 100 -l 200 -g 5 -f 10 -P 2>&1 | tail -1 | sed 's/^/  /'

echo "[th ] after : $(therm)"
echo "==================== lbc-bench done: $label ===================="
