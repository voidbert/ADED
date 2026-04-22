#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for downloading all used models from Hugging Face.
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
#SBATCH --job-name=download-models
#SBATCH --time=00:15:00
#SBATCH --output=output-%j.out
#
# Run on ARM systems
#SBATCH --partition=dev-arm
#SBATCH --account=f202500010hpcvlabuminhoa
#
# Manage number of tasks
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#
# JOB ----------------------------------------------------------------------------------------------

# Downloads a Hugging Face model to the current directory.
#
# Arguments:
#   $1 - Hugging Face user
#   $2 - Model name
#   $3 - Model quantization
download_model() {
    if [ "$1" = 'lm-kit' ]; then
        # This user does not follow correct naming conventions
        file="$(printf "$2" | sed 's/4b-instruct/it-4B/g')"
        wget -qP ../models/ "https://huggingface.co/$1/$2-gguf/resolve/main/$file-$3.gguf"
    else
        wget -qP ../models/ "https://huggingface.co/$1/$2-GGUF/resolve/main/$2-$3.gguf"
    fi
}

# Create directory for models
mkdir -p ../models/

# SmolLM2
download_model 'bartowski' 'SmolLM2-135M-Instruct' 'Q3_K_M'
download_model 'bartowski' 'SmolLM2-135M-Instruct' 'Q4_K_M'
download_model 'bartowski' 'SmolLM2-135M-Instruct' 'Q8_0'

# Gemma3-Instruct-4B
download_model 'lm-kit' 'gemma-3-4b-instruct' 'Q3_K_M'
download_model 'lm-kit' 'gemma-3-4b-instruct' 'Q4_K_M'
download_model 'lm-kit' 'gemma-3-4b-instruct' 'Q8_0'

# Meta-Llama-3.1-Instruct-8B
download_model 'bartowski' 'Meta-Llama-3.1-8B-Instruct' 'Q3_K_M'
download_model 'bartowski' 'Meta-Llama-3.1-8B-Instruct' 'Q4_K_M'
download_model 'bartowski' 'Meta-Llama-3.1-8B-Instruct' 'Q8_0'
