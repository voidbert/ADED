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

from aded.queries.duck import DuckDB
from aded.queries.fastload import FastLoad
from aded.queries.multipass import MultiPass
from aded.queries.original import Original
from aded.queries.postgresql import PostgreSQL
from aded.queries.query import Query
from aded.queries.singlepass import SinglePass

__all__ = [
    'DuckDB',
    'FastLoad',
    'MultiPass',
    'Original',
    'PostgreSQL',
    'Query',
    'SinglePass'
]
