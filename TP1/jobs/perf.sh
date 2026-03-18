#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for measuring performance of all query implementations.
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of Deucalion Job Query.
#
# Deucalion Job Query is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Deucalion Job Query is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Deucalion Job Query.
# If not, see <https://www.gnu.org/licenses/>.
#
# SLURM PROPERTIES ---------------------------------------------------------------------------------
#
# General properties
#SBATCH --job-name=query-perf
#SBATCH --time=01:00:00
#
# Output file
#SBATCH --output=output-%j.out
#
# Run on Arm systems
#SBATCH --partition=normal-arm
#SBATCH --account=f202500010hpcvlabuminhoa
#
# Manage number of tasks
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#
# JOB ----------------------------------------------------------------------------------------------

# Import configuration
. jobs/config.sh

# Load necessary modules
module load Python/3.13.5-GCCcore-14.3.0
module load Java/21.0.8
module load PostgreSQL/16.1-GCCcore-12.3.0

# Enter virtual environment
. "$VENV_PATH/bin/activate"

# Test all query classes
mkdir -p results
for query_class in $PERF_QUERY_CLASSES; do
    echo "Testing: $query_class"

    if [ "$query_class" = "PostgreSQL" ]; then
        initdb "$POSTGRESQL_DATABASE"
        POSTGRES_HOST_AUTH_METHOD=trust postgres -D "$POSTGRESQL_DATABASE" &
        sleep 5 # Wait for PostgreSQL to start up
    fi

    aded/perf.py                       \
        -w "$PERF_WARMUP_RUNS"         \
        -r "$PERF_RUNS"                \
        -o "results/$query_class.json" \
        "$query_class"                 \
        "$DATASET_PATH/$YEAR"

    if [ "$query_class" = "PostgreSQL" ]; then
        pkill "$(jobs -p)"
    fi
done
