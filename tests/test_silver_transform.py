import pytest
import pandas as pd
from pandas.testing import assert_frame_equal

from pipelines.bronze_to_silver import clean_bus_station_data

@pytest.mark.unit
def test_clean_bus_station_data():

    input_data = pd.DataFrame({
        'Name': ['Trạm A', 'Trạm B'],
        'Lat': [10.762, 10.763],
        'Lng': [106.660, 106.661]
    })

    expected_data = pd.DataFrame({
        'Name': ['Trạm A', 'Trạm B'],
        'y': [10.762, 10.763], 
        'x': [106.660, 106.661]  
    })

    actual_data = clean_bus_station_data(input_data)

    assert_frame_equal(actual_data, expected_data)
