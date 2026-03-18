# ABOUT --------------------------------------------------------------------------------------------
#
# Configuration for Deucalion jobs.
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
# CONFIGURATION ------------------------------------------------------------------------------------

# Path to the Python virtual environment. Will be automatically created by setup-env.sh.
VENV_PATH=".venv"

# Path to the original dataset, that will be copied.
ORIGINAL_DATASET_PATH="/projects/F202500010HPCVLABUMINHO/DataSets/Reports"

# Path where the original dataset will be copied to. Used in normal query runs.
DATASET_PATH="dataset"

# Year of the dataset to process.
YEAR="2025"

# Path to the PostgreSQL database that will be created for testing the PostgreSQL query.
POSTGRESQL_DATABASE="/tmp/aded-postgres"

# Space-separated list of query classes to measure performance of
PERF_QUERY_CLASSES="Original MultiPass SinglePass FastLoad PostgreSQL DuckDB"

# Number of runs per query class
PERF_RUNS=5

# Number of warmum runs per query class
PERF_WARMUP_RUNS=5
