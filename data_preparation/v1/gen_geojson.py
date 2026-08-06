from pathlib import Path
import geojson
import geopandas as gpd

from data_preparation.utils import put_geojson, log_geojson, get_s3

def read_geojson(name):
    return geojson.load(get_s3(name))

def merge_polygons(p1, p2):
    assert len(p1) == 1 and len(p2) == 1  # Single polygons
    assert len(p1[0]) == 1 and len(p2[0]) == 1  # No holes
    ring1 = p1[0][0]
    ring2 = p2[0][0]
    shared1 = [i for i, e in enumerate(ring1[:-1]) if e in ring2]
    shared2 = [i for i, e in enumerate(ring2[:-1]) if e in ring1]
    assert len(shared1) == len(shared2)
    assert len(shared1) > 0
    assert all(shared1[i+1] == shared1[i]+1 for i in range(len(shared1)-1))
    assert all(shared2[i+1] == shared2[i]+1 for i in range(len(shared2)-1))
    assert all(ring1[shared1[i]] == ring2[shared2[-1-i]] for i in range(len(shared1)))
    return [[ring1[:shared1[0]] + ring2[shared2[-1]:] + ring2[:shared2[0]] + ring1[shared1[-1]:]]]

# PATH_TO_DATA = Path(__file__).parent.resolve() / "data"
# assert PATH_TO_DATA.exists()

# PATH_TO_TESTDATA = Path(__file__).resolve().parent.parent / "testdata" / "overtourism-data"
# assert PATH_TO_TESTDATA.exists()

def gen_geojson():
    geojson_comuni = read_geojson('ComuniTrentini.geojson')
    for feature in geojson_comuni["features"]:
        feature["properties"]["com_code"] = feature["properties"]["com_code"].lstrip("0")

    geojson_voda = read_geojson('TRENTINO-comuni_Vodafone_2023.geojson')
    f_vigo = None
    f_pozza = None
    f_s_giovanni = None
    for f in geojson_voda["features"]:
        f["properties"]["name"] = f["properties"]["name"].upper()
        match f["properties"]["name"]:
            case "VIGO DI FASSA":
                f_vigo = f
            case "POZZA DI FASSA":
                f_pozza = f
            case "SAN GIOVANNI DI FASSA":
                f_s_giovanni = f
            case _:
                pass
    assert f_vigo is not None and f_pozza is not None and f_s_giovanni is None
    assert f_vigo["geometry"]["type"] == "MultiPolygon" and f_pozza["geometry"]["type"] == "MultiPolygon"
    f_s_giovanni_coordinates = merge_polygons(f_vigo["geometry"]["coordinates"], f_pozza["geometry"]["coordinates"])
    geojson_voda["features"].append(dict(
        type="Feature",
        geometry=dict(type="MultiPolygon", coordinates=f_s_giovanni_coordinates),
        properties=dict(id="9999", prov="22", name="SAN GIOVANNI DI FASSA", label="", desc="San Giovanni di Fassa"),
    ))

    geojson_apt = read_geojson('TRENTINO-apt_2023.geojson')
    apt_map={
        100:"San Martino di Castrozza, Primiero e Vanoi",
        101:"Val di Non",
        102:"Rovereto, Vallagarina e Monte Baldo",
        103:"Val di Fassa",
        104:"Val di Sole",
        105:"Altopiano della Paganella, Piana della Rotaliana e San Lorenzo Dorsino",
        106:"Madonna di Campiglio, Pinzolo, Val Rendena, Giudicarie centrali e Valle del Chiese",
        107:"Val di Fiemme e Val di Cembra",
        108:"Valsugana, Tesino e Valle dei Mocheni",
        109:"Trento, Monte Bondone e Altopiano di Pinè",
        110:"Garda trentino, Valle di Ledro, Terme di Comano e Valle dei Laghi",
        111:"Altipiani cimbri e Vigolana",
    }
    for f in geojson_apt["features"]:
        f["properties"]["name"] = apt_map.get(f["properties"]["id"], f["properties"]["name"])

    return (gpd.GeoDataFrame.from_file(geojson_comuni),
            gpd.GeoDataFrame.from_file(geojson_voda),
            gpd.GeoDataFrame.from_file(geojson_apt))

def main():
    geojson_comuni, geojson_voda, geojson_apt = gen_geojson()

    log_geojson(geojson_comuni, "map_comuni")
    log_geojson(geojson_voda, "map_vodafone")
    log_geojson(geojson_apt, "map_apt")

def local():
    geojson_comuni, geojson_voda, geojson_apt = gen_geojson()

    put_geojson(geojson_comuni, "map_comuni")
    put_geojson(geojson_voda, "map_vodafone")
    put_geojson(geojson_apt, "map_apt")

if __name__ == ("__main__"):
    local()