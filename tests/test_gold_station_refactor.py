"""
Tests for the refactored bus_station_data handling in 3.2_data_mining_gold.py.
Validates that 2-way (Outbound/Inbound) station data is processed correctly.

Run with:  pytest tests/test_gold_station_refactor.py -v
"""
import pytest
import pandas as pd
import json
import os
import sys
import importlib.util

# Load the module with non-standard filename (dots in name)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

spec = importlib.util.spec_from_file_location(
    "gold", os.path.join(_PROJECT_ROOT, "pipelines", "3.2_data_mining_gold.py")
)
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)


# ============================================================
# 1. Tests for create_stops_from_silver()
# ============================================================
class TestCreateStopsFromSilver:
    """Validates deduplication of stations across Outbound & Inbound."""

    def _make_station_df(self, rows):
        """Helper: build a DataFrame that mimics silver station data."""
        return pd.DataFrame(rows)

    def test_dedup_merges_routes_from_both_directions(self):
        """Same station in Outbound and Inbound should be merged into one row."""
        df = self._make_station_df([
            {"Name": "Trạm A", "Routes": "50,91"},
            {"Name": "Trạm A", "Routes": "50,32"},   # same station, Inbound direction
            {"Name": "Trạm B", "Routes": "50"},
        ])

        result = gold.create_stops_from_silver(df)

        # Should have 2 unique stations, not 3
        assert len(result) == 2
        
        # Trạm A should have merged routes: {32, 50, 91}
        row_a = result[result["Name"] == "Trạm A"].iloc[0]
        routes_set = set(r.strip() for r in row_a["Routes"].split(",") if r.strip())
        assert routes_set == {"50", "91", "32"}

    def test_filters_invalid_routes(self):
        """Routes not in the valid_routes set should be stripped out."""
        df = self._make_station_df([
            {"Name": "Trạm C", "Routes": "50,999,FAKE"},
        ])

        result = gold.create_stops_from_silver(df)
        row = result[result["Name"] == "Trạm C"].iloc[0]
        assert row["Routes"] == "50"  # only valid route kept

    def test_single_direction_no_change(self):
        """A station appearing only once (single direction) should pass through."""
        df = self._make_station_df([
            {"Name": "Trạm D", "Routes": "3,45"},
        ])

        result = gold.create_stops_from_silver(df)
        assert len(result) == 1
        routes = set(r.strip() for r in result.iloc[0]["Routes"].split(","))
        assert routes == {"3", "45"}


# ============================================================
# 2. Tests for re_split_trips_by_route()
# ============================================================
class TestReSplitTripsByRoute:
    """Validates station_index merge with Outbound-first, Inbound-fallback."""

    @pytest.fixture
    def station_json(self, tmp_path):
        """Create a temporary bus_station.json with 2-way data."""
        data = [
            {
                "RouteID": "50",
                "Way": "Outbound",
                "Stations": [
                    {"Name": "Bến Thành"},
                    {"Name": "Chợ Lớn"},
                    {"Name": "Phú Lâm"},
                ]
            },
            {
                "RouteID": "50",
                "Way": "Inbound",
                "Stations": [
                    {"Name": "Phú Lâm"},
                    {"Name": "Bình Tây"},   # Inbound-only station
                    {"Name": "Bến Thành"},
                ]
            },
            {
                "RouteID": "70-5",
                "Stations": [  # No Way field — legacy entry
                    {"Name": "Bố Heo"},
                    {"Name": "Bến xe Lộc Hưng"},
                ]
            },
        ]
        path = tmp_path / "bus_station.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _make_gps_df(self, rows):
        """Helper: build a minimal GPS DataFrame for re_split_trips_by_route."""
        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    def test_outbound_station_gets_correct_index(self, station_json):
        """Stations found in Outbound should get Outbound index."""
        df = self._make_gps_df([
            {"vehicle": "V1", "trip_id": 1, "inferred_route": "50", "current_station": "Bến Thành",
             "datetime": "2026-01-01 08:00:00", "speed": 30, "is_terminal": False, "station_distance": 50},
            {"vehicle": "V1", "trip_id": 1, "inferred_route": "50", "current_station": "Chợ Lớn",
             "datetime": "2026-01-01 08:10:00", "speed": 30, "is_terminal": False, "station_distance": 50},
        ])

        result = gold.re_split_trips_by_route(df, station_json, drop_threshold=5, max_gap_seconds=1800)

        # Should not crash; station_index column should be cleaned up
        assert "station_index" not in result.columns
        assert len(result) == 2

    def test_inbound_only_station_falls_back(self, station_json):
        """A station that exists ONLY in Inbound should still get an index via fallback."""
        df = self._make_gps_df([
            {"vehicle": "V2", "trip_id": 1, "inferred_route": "50", "current_station": "Bình Tây",
             "datetime": "2026-01-01 09:00:00", "speed": 25, "is_terminal": False, "station_distance": 40},
            {"vehicle": "V2", "trip_id": 1, "inferred_route": "50", "current_station": "Bến Thành",
             "datetime": "2026-01-01 09:15:00", "speed": 25, "is_terminal": False, "station_distance": 30},
        ])

        # The key test: "Bình Tây" only exists in Inbound, so the fallback merge must fire.
        # If the fallback didn't work, station_index would be -1 and trip splitting would be wrong.
        result = gold.re_split_trips_by_route(df, station_json, drop_threshold=5, max_gap_seconds=1800)
        assert len(result) == 2  # no rows dropped

    def test_legacy_route_without_way_field(self, station_json):
        """Routes without 'Way' field (70-5, 61-7) should default to Outbound."""
        df = self._make_gps_df([
            {"vehicle": "V3", "trip_id": 1, "inferred_route": "70-5", "current_station": "Bố Heo",
             "datetime": "2026-01-01 10:00:00", "speed": 20, "is_terminal": False, "station_distance": 30},
        ])

        result = gold.re_split_trips_by_route(df, station_json, drop_threshold=5, max_gap_seconds=1800)
        assert len(result) == 1
