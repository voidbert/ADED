#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for obtaining all models' responses for all prompts, for further human evaluation.
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
RESPONSES_DIR='../responses'

# llama.cpp build to use (build directory name)
LLAMA_CPP_BUILD_CONFIGURATION='build-clang-cpu'

# Seed to be used for all prompts
SEED=123

# Maximum number of tokens per reply
MAX_TOKENS=4096

# JOB ----------------------------------------------------------------------------------------------

# Load necessary modules
module purge
module load GCC/13.3.0
module load LLVM/19.1.7-GCCcore-13.3.0
module load CMake/3.31.3-GCCcore-13.3.0
module load BLIS/1.0-GCC-13.3.0

# Create a temporary file for llama.cpp API response
trap 'rm "$api_response_file" 2> /dev/null' HUP INT TERM QUIT EXIT
api_response_file="$(mktemp)"

for model in $(find '../models' -type f); do
    # Run llama.cpp's server in the background
    "../llama.cpp/$LLAMA_CPP_BUILD_CONFIGURATION/bin/llama-server" -m "$model" 2>/dev/null &

    # Wait for the model to load
    while [ "$(curl -s 'http://localhost:8080/health' | jq -r '.status')" != 'ok' ]; do
        sleep 1
    done

    # Ask the model for a response for all prompts
    for prompt in $(find '../prompts' -type f | sort); do
        # Create a directory for storing the response to the current prompt
        prompt_type="$(basename "$(dirname "$prompt")")"
        prompt_output_directory="$RESPONSES_DIR/$(basename "$model")/$prompt_type"
        mkdir -p "$prompt_output_directory"

        # Progress message
        printf 'Processing %s: %s\n' "$(basename "$model")" "$prompt_type/$(basename "$prompt")"

        # Obtain reponse from the model
        prompt_contents="$(cat "$prompt" | sed 's/"/\"/g')"
        curl -s 'http://localhost:8080/v1/chat/completions' \
            --data '{
                "messages": [
                    {
                        "role": "user",
                        "content": "'"$prompt_contents"'"
                    }
                ],
                "seed": '"$SEED"',
                "max_tokens": '"$MAX_TOKENS"'
            }' > "$api_response_file"

        # Place responses in correct files
        jq -r '.choices[0].message.content' "$api_response_file" > \
            "$prompt_output_directory/$(basename "$prompt")"
    done

    # Stop the llama.cpp server
    pkill llama-server
done
