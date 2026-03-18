# ABOUT --------------------------------------------------------------------------------------------
#
# Configuration for different aspects of the application.
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
# CONFIG FILE --------------------------------------------------------------------------------------

import getpass
import socket

# Hardcoded year for validator and performance analysis report results. It only influences output
# parameters related to time ranges, so it need not be changed for using other years' datasets.
YEAR = 2025

# Hardcoded month (1-12) for performance analysis reports.
MONTH = 1

# Maxmimum allowed relative floating-point error (0.1 %) in output validation
MAX_RELATIVE_ERROR = 0.001

# String to be prepended to all file paths sent to PostgreSQL. By default:
#
#  - Path are not changed on Deucalion Arm nodes (cna)
#  - Paths are prepended with '/mnt' otherwise. Please mount the host's / on the container's /mnt.
POSTGRES_PATH_PREFIX = '' if socket.gethostname().startswith('cna') else '/mnt'

# User for PostgreSQL connection. By default, the current username is used on Deucalion, and
# Docker's 'postgres' is used elsewhere.
POSTGRES_USER = getpass.getuser() if socket.gethostname().startswith('cna') else 'postgres'

# Network interface to monitor. By default, only Deucalion's /dev/ib0 is monitored.
NETWORK_INTERFACE = 'ib0' if socket.gethostname().startswith('cna') else None
