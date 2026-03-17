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
    import multipass
    import singlepass
    import fastload
    import postgresql
    import duck

    return {
        'Original':   original.Original,
        'MultiPass':  multipass.MultiPass,
        'SinglePass': singlepass.SinglePass,
        'FastLoad':   fastload.FastLoad,
        'PostgreSQL': postgresql.PostgreSQL,
        'DuckDB':     duck.DuckDB
    }

# Returns how many threads should be used by the context (Spark, database, ...)
def get_context_threads() -> int:
    threads_str = os.environ.get('CONTEXT_NTHREADS', '1')

    try:
        return int(threads_str)
    except ValueError:
        print(f'CONTEXT_NTHREADS is an invalid number of threads: {threads_str}. Defaulting to 1.')
        return 1
