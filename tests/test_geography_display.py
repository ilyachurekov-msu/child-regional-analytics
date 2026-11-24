from app.services.geography import geography, plotly_geography


def test_display_winding_does_not_mutate_original_geometry():
    original, _ = geography()
    display, _ = plotly_geography()
    before = next(f for f in original['features'] if f['properties']['region_id'] == 'RU-77')['geometry']['coordinates'][0][0]
    after = next(f for f in display['features'] if f['properties']['region_id'] == 'RU-77')['geometry']['coordinates'][0][0]
    assert after == list(reversed(before))
    assert original is not display
