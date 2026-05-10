#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for obtaining all models' responses for all prompts, for further human evaluation.
# Usage: ./quality-test.sh
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

# Directory where to store prompt responses
RESPONSES_DIR='../results/responses'

# llama.cpp build to use (build directory name)
LLAMA_CPP_BUILD_CONFIGURATION='build-clang-cpu'

# Seed to be used for all prompts
SEED=0

# Maximum number of tokens per reply
MAX_TOKENS=4096

# JOB ----------------------------------------------------------------------------------------------

# Parse command-line arguments
if [ "$#" = 0 ]; then
    # Not a Slurm job. Relaunch the script as a job for testing multiple models in parallel.
    mkdir -p "$RESPONSES_DIR"
    find '../models' -type f | while IFS= read -r model_file; do
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
    model_name="$(basename "$model_file" | sed 's/\.gguf$//')"

    # Create a temporary file for llama.cpp API responses
    trap 'rm "$api_response_file" 2> /dev/null' HUP INT TERM QUIT EXIT
    api_response_file="$(mktemp)"

    # Start llama.cpp's server in the background and wait for the model to load
    "../llama.cpp/$LLAMA_CPP_BUILD_CONFIGURATION/bin/llama-server" -m "$model_file" 2>/dev/null &
    while [ "$(curl -s 'http://localhost:8080/health' | jq -r '.status')" != 'ok' ]; do
        sleep 1
    done

    # Ask the model for a response for all prompts
    find '../prompts' -type f | sort | while IFS= read -r prompt_file; do
        escaped_prompt="$(sed 's/"/\\"/g' < "$prompt_file")"

        # Create a directory for storing the response to the current prompt
        prompt_type="$(basename "$(dirname "$prompt_file")")"
        prompt_output_directory="$RESPONSES_DIR/$model_name/$prompt_type"
        mkdir -p "$prompt_output_directory"

        # Progress message
        printf '%s: Processing %s: %s\n'              \
            "$(date +%H:%M:%S)"                       \
            "$model_name"                             \
            "$prompt_type/$(basename "$prompt_file")"

        # Obtain reponse from the model
        curl -s 'http://localhost:8080/v1/chat/completions' \
            --data '{
                "messages": [
                    {
                        "role": "user",
                        "content": "'"$escaped_prompt"'"
                    }
                ],
                "seed": '"$SEED"',
                "max_tokens": '"$MAX_TOKENS"'
            }' > "$api_response_file"

        # Place responses in correct files
        jq -r '.choices[0].message.content' "$api_response_file" > \
            "$prompt_output_directory/$(basename "$prompt_file")"
    done

    # Stop the llama.cpp server
    pkill llama-server
fi
