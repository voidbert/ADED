#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for testing if model performance varies with --mmap. `--no-mmap` data must be
# taken from `warmup-test.sh` to avoid rerunning tests.
#
# Usage: $ ./mmap-test.sh
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of FastInference.
#
# FastInference is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# FastInference is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with FastInference. If
# not, see <https://www.gnu.org/licenses/>.
#
# SLURM PROPERTIES ---------------------------------------------------------------------------------
#
# General properties
#SBATCH --job-name=quality-test
#SBATCH --time=01:00:00
#SBATCH --output=output-%j.out
#
# Run on ARM systems
#SBATCH --partition=normal-arm
#SBATCH --account=f202500010hpcvlabuminhoa
#
# Manage number of tasks
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#
# CONFIGURATION ------------------------------------------------------------------------------------

# Directory where to output the mmap results to
OUTPUT_DIRECTORY='../results/mmap'

# llama.cpp build to test
LLAMA_CPP_BUILD_CONFIGURATION='build-clang-blis'

# Model quantizations to test
QUANTIZATION='Q4_K_M'

# Seed to be used for all prompts
SEED=0

# Number of runs per prompt and model
RUNS=10

# Maximum number of tokens per reply
MAX_TOKENS=4096

# JOB ----------------------------------------------------------------------------------------------

# Parse command-line arguments
if [ "$#" = 0 ]; then
    # Not a Slurm job. Relaunch the script as a job for testing multiple models in parallel.
    mkdir -p "$OUTPUT_DIRECTORY"
    find '../models' -type f -name "*$QUANTIZATION*" | while IFS= read -r model_file; do
        sbatch "$0" "$model_file"
    done
else
    # Load necessary modules
    module purge
    module load GCC/13.3.0
    module load LLVM/19.1.7-GCCcore-13.3.0
    module load CMake/3.31.3-GCCcore-13.3.0
    module load BLIS/1.0-GCC-13.3.0

    # Script is being run as a Slurm job for testing a single model
    model_file="$1"
    model_name="$(basename "$model_file" | sed -E 's/\-Q[0-9_KM]+\.gguf$//')"
    quantization="$(basename "$model_file" | grep -Eo -- 'Q[0-9_KM]+')"
    output_file="$OUTPUT_DIRECTORY/$model_name-$quantization.csv"

    # Write output CSV file header
    printf 'COMPILER,MODEL,QUANTIZATION,SEEDING,PROMPT,RUN,' >  "$output_file"
    printf 'PROMPT_N,PREDICTED_N,CACHE_N,TTFT,TPOT,MEM\n'    >> "$output_file"

    # Ask the model for multiple responses for a prompt of each category
    find '../prompts' -type f -name '0' | sort -r | while IFS= read -r prompt_file; do
        escaped_prompt="$(sed 's/"/\\"/g' < "$prompt_file")"
        prompt_type="$(basename "$(dirname "$prompt_file")")"

        # Run llama.cpp's server in the background. llama.cpp is restarted for every prompt to avoid
        # KV-cache reuse between prompts.
        "../llama.cpp/$LLAMA_CPP_BUILD_CONFIGURATION/bin/llama-server" \
            --mmap -m "$model_file" 2>/dev/null &

        # Wait for the model to load
        while [ "$(curl -s 'http://localhost:8080/health' | jq -r '.status')" != 'ok' ]; do
            sleep 1
        done

        # Provide the same prompt multiple times to the model
        for run in $(seq "$RUNS"); do
            # Progress message
            printf '%s -> Processing %s: %s (run %s)\n' \
                "$(date +%H:%M:%S)"                     \
                "$model_name-$quantization"             \
                "$prompt_type"                          \
                "$run"

            # Write run information to output file
            printf '%s,%s,%s,%s,%s,%s,'                \
                "$LLAMA_CPP_BUILD_CONFIGURATION"       \
                "$model_name" "$quantization" 'static' \
                "$prompt_type" "$run"                  >> "$output_file"

            # Obtain reponse from the model and output timing metrics
            curl -s 'http://localhost:8080/v1/chat/completions' --data '{
                "messages": [
                    {
                        "role": "user",
                        "content": "'"$escaped_prompt"'"
                    }
                ],
                "seed": '"$SEED"',
                "max_tokens": '"$MAX_TOKENS"'
            }' | jq -r '
                .timings |
                    "\(.prompt_n),\(.predicted_n),\(.cache_n)," +
                    "\(.prompt_ms + .predicted_per_token_ms),\(.predicted_per_token_ms),"
            '  | tr -d '\n' >> "$output_file"

            # Get system memory usage in bytes
            free -b | grep '^Mem:' | awk '{ printf "%s\n", $3 }' >> "$output_file"
        done

        # Stop the llama.cpp server
        pkill llama-server
    done
fi
