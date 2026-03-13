# ABOUT --------------------------------------------------------------------------------------------
#
# Utility functions for query-running programs.
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
# SOURCE FILE --------------------------------------------------------------------------------------

import os
import sys

from query import Query

# Returns all available query implementation classes
def get_avaialable_queries() -> dict[str, type[Query]]:
    import original
    import duck

    return {query.__name__: query for query in Query.__subclasses__()} # type: ignore

# Returns how many Spark processes should be used
def get_spark_num_processes() -> int:
    processes_str = os.environ.get('SPARK_NPROC', '1')

    try:
        return int(processes_str)
    except ValueError:
        print(f'SPARK_NPROC contains invalid number of processes:', processes_str)
        return 1
