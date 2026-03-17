# ABOUT --------------------------------------------------------------------------------------------
#
# Abstraction for reusable PostgreSQL connection.
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
import psycopg2

from aded import config
from aded.contexts.context import Context

# Abstraction for reusable PostgreSQL connection.
class PostgreSQLContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Connect to a local database
        self.connection = psycopg2.connect(
            host='localhost',
            port=5432,
            database='postgres',
            user='postgres'
        )

        self.cursor = self.connection.cursor()

    def between_runs_cleanup(self) -> None:
        # Delete all temporary tables
        self.cursor.execute('DISCARD TEMP')

    def final_cleanup(self) -> None:
        self.cursor.close()
        self.connection.close()

    # Converts a file path to one that can be used in PostgreSQL.
    def convert_file_path(self, path: str) -> str:
        return config.POSTGRES_PATH_PREFIX + os.path.abspath(path)
