import math
import sys
from pathlib import Path

import requests

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

PLANET_IDENTIFIERS: dict[str, str] = {
    "MERCURY": "199",
    "VENUS":   "299",
    "EARTH":   "399",
    "MARS":    "499",
    "JUPITER": "599",
    "SATURN":  "699",
    "URANUS":  "799",
    "NEPTUNE": "899",
}

PLANET_PROPERTIES: dict[str, dict[str, str]] = {}

def fetch_data(outdir: Path | None = None) -> None:
    outdir = outdir or Path(__file__).parent / "data"
    outdir.mkdir(parents=True, exist_ok=True)

    for planet, identifier in PLANET_IDENTIFIERS.items():
        resp = requests.get(HORIZONS_URL, params = {
            "format":       "text",
            "COMMAND":      f"'{identifier}'",
            "EPHEM_TYPE":   "'VECTORS'",
            "CENTER":       "'500@0",
            "START_TIME":   "'2023-02-25",
            "STOP_TIME":    "'2187-12-01'",
            "STEP_SIZE":    "'1 d'",
            "VEC_TABLE":    "'2'",
            "VEC_LABELS":   "'NO'",
            "OUT_UNITS":    "'AU-D'",
            "CSV_FORMAT":   "'YES'",
        }, timeout=15)

        data_file = outdir / f"{planet}.txt"
        with open(data_file, "w") as f:
            print(f"Fetch {planet}: {data_file}")
            f.write(resp.text)
        f.close()


def parse_data(datadir: Path | str = Path(__file__).parent / "data") -> dict[str, dict[str, str]]:
    _ENTRY_ORDER: list[str] = [
        "JDTDB",
        "Calendar Date",
        "X",
        "Y",
        "Z",
        "VX",
        "VY",
        "VZ",
    ]
    # {"planet": {"X": xpos, "Y": ypos}}
    positions: dict[str, dict[str, float]] = {}

    datadir = Path(datadir)
    if not datadir.exists():
        raise FileNotFoundError(datadir)

    for planet in PLANET_IDENTIFIERS:
        contents = (datadir / f"{planet}.txt").read_text()
        body = contents.split("$$SOE")[1].split("$$EOE")[0].strip()

        #print(f"Parse: {planet}: {body}")

        PLANET_PROPERTIES[planet] = [
            dict(zip(_ENTRY_ORDER, (field.strip() for field in line.split(",")))) for line in body.splitlines() if line.strip()
        ]
    
    # carve out only needed data (x and y vectors per planet)
    for planet, properties in PLANET_PROPERTIES.items():
        posx = float(properties[0]["X"])
        posy = float(properties[0]["Y"])
        positions[str(planet)] = {"X": posx, "Y": posy}
    #print(positions)

    return positions
    
def calculate_distances(parsed_data: dict[str, dict[str, str]]):
    distances: list[dict[str, [dict[str, float]]]] = {} # [MARS: {"Earth": dist_to_earth}, "Jupiter": dist_to_jupit]
    # calculate distances
    for planet, pos in parsed_data.items():
        distances[planet] = {}
        p1 = [pos["X"], pos["Y"]]           # vector
        for target_planet in PLANET_IDENTIFIERS:
            if planet == target_planet:
                continue
            p2 = [parsed_data[target_planet]["X"], parsed_data[target_planet]["Y"]] # vector
            
            p1p2 = [p2[0] - p1[0], p2[1] - p1[1]]

            dist = math.sqrt(math.pow(p1p2[0], 2) + math.pow(p1p2[1], 2))
            distances[planet][target_planet] = round(dist, 6)
        
    #print(distances)
    return distances
        
def generate_json(distances):
    import json
    with open(Path(__file__).parent / "out.json", "w") as f:
        json.dump(distances, f, indent=4, ensure_ascii=True)
    
    f.close()

def generate_csv(distances):
    import csv
    with open(Path(__file__).parent / "out.csv", "w", newline="") as f:
        idx = {p: i for i, p in enumerate(PLANET_IDENTIFIERS.keys())}
        writer = csv.writer(f)
        for a in PLANET_IDENTIFIERS:
            for b, d in distances[a].items():
                if idx[a] < idx[b]:
                    writer.writerow([a, b, round(d, 6)])

def main() -> None:
    argv = sys.argv

    # don't fetch every rerun
    def routine():
        return calculate_distances(parse_data())

    match argv[1:]:
        case []:
            routine()

        case ['fetch']:
            fetch_data()

        case ['json']:
            generate_json(routine())

        case ['csv']:
            generate_csv(routine())

if __name__ == "__main__":
    main()