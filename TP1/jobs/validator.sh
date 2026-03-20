#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for validating query output.
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
#SBATCH --job-name=query-validator
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

# Get the query class from the command line argument
QUERY_CLASS=$1

if [ -z "$QUERY_CLASS" ]; then
    echo "Usage: sbatch jobs/validator.sh <QueryClass>"
    exit 1
fi

echo "Validating: $QUERY_CLASS"

if [ "$QUERY_CLASS" = "PostgreSQL" ]; then
    initdb "$POSTGRESQL_DATABASE"
    POSTGRES_HOST_AUTH_METHOD=trust postgres -D "$POSTGRESQL_DATABASE" &
    sleep 5
fi

python aded/validator.py "$QUERY_CLASS" "$DATASET_PATH/$YEAR"

if [ "$QUERY_CLASS" = "PostgreSQL" ]; then
    pkill -P $$ 
fi
