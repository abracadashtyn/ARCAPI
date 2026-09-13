#!/bin/bash

START_TIME=$(date +%s)
START_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "========================================="
echo "Job started at ${START_TIMESTAMP}"

source /root/ReplayGenieAPI/.env.production
cd /root/ReplayGenieAPI

echo "-----------------------------------------"
echo "Begin ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-B' (ID=10)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 10
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-B' (ID=10) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME

echo "-----------------------------------------"
echo "Begin ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-C' (ID=11)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 11
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-C' (ID=11) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME



echo "-----------------------------------------"
echo "Begin ingesting matches for format '[Gen 9] OU' (ID=4)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 4
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] OU' (ID=4) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME

echo "-----------------------------------------"
echo "Begin ingesting matches for format '[Gen 9] Doubles OU' (ID=5)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 5
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] Doubles OU' (ID=5) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME

echo "-----------------------------------------"
echo "Begin ingesting matches for lower tier Gen 9 formats (IDs=6,7,8,9)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 6
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 7
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 8
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 9
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] Doubles OU' (ID=5) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME

echo "-----------------------------------------"
echo "Assigning sets to all newly ingested matches for format '[Gen 9 Champions] VGC 2026 Reg M-C' (ID=11)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 11
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assiging sets to matches for format '[Gen 9 Champions] VGC 2026 Reg M-C' (ID=11) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"
PREV_JOB_END = END_TIME

echo "-----------------------------------------"
echo "Assigning sets to all newly ingested matches for format '[Gen 9 Champions] VGC 2026 Reg M-B' (ID=10)"
echo "-----------------------------------------"
/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 10
EXIT_CODE=$?
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - PREV_JOB_END))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assiging sets to matches for format '[Gen 9 Champions] VGC 2026 Reg M-B' (ID=10) at ${END_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${EXIT_CODE}"
echo "-----------------------------------------"

END_ALL_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))
echo "-----------------------------------------"
echo "Job completed at ${END_ALL_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${TOTAL_DURATION} seconds)"
echo "========================================="
echo ""
