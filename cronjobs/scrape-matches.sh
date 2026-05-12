#!/bin/bash

START_TIME=$(date +%s)
START_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "========================================="
echo "Job started at ${START_TIMESTAMP}"
echo "-----------------------------------------"

source /root/ReplayGenieAPI/.env.production
cd /root/ReplayGenieAPI


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 2
F2_EXIT_CODE=$?
END_F2_TIME=$(date +%s)
END_F2_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F2_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done ingesting matches for format '[Gen 9] VGC 2026 Reg I' at ${END_F2_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${F2_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown scrape -f 3
F3_EXIT_CODE=$?
END_F3_TIME=$(date +%s)
END_F3_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_F3_TIME - END_F2_TIME))
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


/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 2
FS2_EXIT_CODE=$?
END_FS2_TIME=$(date +%s)
END_FS2_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_FS2_TIME - END_F5_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assigning set ids to all newly ingested matches with format_id=2 at ${END_FS2_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${FS2_EXIT_CODE}"
echo "-----------------------------------------"


/root/ReplayGenieAPI/venv/bin/flask showdown assign-set -f 3
FS3_EXIT_CODE=$?
END_FS3_TIME=$(date +%s)
END_FS3_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_FS3_TIME - END_FS2_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Done assigning set ids to all newly ingested matches with format_id=3 at ${END_FS3_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "Exit code: ${FS3_EXIT_CODE}"
echo "-----------------------------------------"



TOTAL_DURATION=$((END_FS3_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))
echo "-----------------------------------------"
echo "Job completed at ${END_P3_TIMESTAMP}"
echo "Duration: ${MINUTES}m ${SECONDS}s (${DURATION} seconds)"
echo "========================================="
echo ""
