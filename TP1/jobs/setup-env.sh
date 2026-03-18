#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for copying the dataset and setting up the Python virtual envrionment.
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
#SBATCH --job-name=setup-env
#SBATCH --time=00:10:00
#
# Output file
#SBATCH --output=output-%j.out
#
# Run on Arm systems
#SBATCH --partition=dev-arm
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

# Copy the dataset to the current directory and fix dataset issues
cp -r "$ORIGINAL_DATASET_PATH" "$DATASET_PATH"
mv "$DATASET_PATH/2025/jobs_Ago.txt" "$DATASET_PATH/2025/jobs_Aug.txt"

# Create virtual environment and install required packages
python -m venv "$VENV_PATH"
. "$VENV_PATH/bin/activate"
pip install -e .
