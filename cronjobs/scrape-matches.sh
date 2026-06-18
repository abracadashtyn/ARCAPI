#!/bin/bash

START_TIME=$(date +%s)
START_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "========================================="
echo "Job started at ${START_TIMESTAMP}"
echo "-----------------------------------------"

source /root/ReplayGenieAPI/.env.production
cd /root/ReplayGenieAPI


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 10
F10_EXIT_CODE=$?
END_F10_TIME=$(date +%s)
END_F10_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F10_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-B' at ${END_F10_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${F10_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 3
F3_EXIT_CODE=$?
END_F3_TIME=$(date +%s)
END_F3_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F3_TIME - END_F10_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9 Champions] VGC 2026 Reg M-A' at ${END_F3_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${F3_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 4
F4_EXIT_CODE=$?
END_F4_TIME=$(date +%s)
END_F4_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F4_TIME - END_F3_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] OU' at ${END_F4_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${F4_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 5
F5_EXIT_CODE=$?
END_F5_TIME=$(date +%s)
END_F5_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F5_TIME - END_F4_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] Doubles OU' at ${END_F5_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${F5_EXIT_CODE}"
echo "-----------------------------------------"

/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 6
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 7
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 8
/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 9
LOWER_EXIT_CODE=$?
END_LOWER_TIME=$(date +%s)
END_LOWER_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_LOWER_TIME - END_F5_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for less common gen 9 formats at ${END_LOWER_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${LOWER_EXIT_CODE}"
echo "-----------------------------------------"

/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 10
FS10_EXIT_CODE=$?
END_FS10_TIME=$(date +%s)
END_FS10_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_FS10_TIME - END_LOWER_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assigning set ids to all newly ingested matches with format_id=10 at ${END_FS10_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${FS10_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 3
FS3_EXIT_CODE=$?
END_FS3_TIME=$(date +%s)
END_FS3_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_FS3_TIME - END_FS10_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assigning set ids to all newly ingested matches with format_id=3 at ${END_FS3_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${FS3_EXIT_CODE}"
echo "-----------------------------------------"


END_ALL_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_DURATION=$((END_FS3_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))
echo "-----------------------------------------"
echo "Job completed at ${END_ALL_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${TOTAL_DURATION} seconds)"
echo "========================================="
echo ""
