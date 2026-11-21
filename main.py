import math
import sys
from pathlib import Path

import requests

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

PLANET_IDENTIFIERS: dict[str, str] = {
    "MERCURY": "199",
    "VENUS": "299",
    "EARTH": "399",
    "MARS": "499",
    "JUPITER": "599",
    "SATURN": "699",
    "URANUS": "799",
    "NEPTUNE": "899",
}

PLANET_PROPERTIES: dict[str, dict[str, str]] = {}


def fetch_data(outdir: Path | None = None) -> None:
    outdir = outdir or Path(__file__).parent / "data"
    outdir.mkdir(parents=True, exist_ok=True)

    for planet, identifier in PLANET_IDENTIFIERS.items():
        resp = requests.get(
            HORIZONS_URL,
            params={
                "format": "text",
                "COMMAND": f"'{identifier}'",
                "EPHEM_TYPE": "'VECTORS'",
                "CENTER": "'500@0'",
                "START_TIME": "'2023-02-25'",
                "STOP_TIME": "'2187-12-01'",
                "STEP_SIZE": "'1 d'",
                "VEC_TABLE": "'2'",
                "VEC_LABELS": "'NO'",
                "OUT_UNITS": "'AU-D'",
                "CSV_FORMAT": "'YES'",
            },
            timeout=15,
        )

        data_file = outdir / f"{planet}.txt"
        with open(data_file, "w") as f:
            print(f"Fetch {pstr(planet)} {data_file}")
            f.write(resp.text)
        f.close()


def parse_data(
    datadir: Path | str = Path(__file__).parent / "data",
) -> dict[str, dict[str, str]]:
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

        # print(f"Parse: {planet}: {body}")

        PLANET_PROPERTIES[planet] = [
            dict(zip(_ENTRY_ORDER, (field.strip() for field in line.split(","))))
            for line in body.splitlines()
            if line.strip()
        ]

    # carve out only needed data (x and y vectors per planet)
    for planet, properties in PLANET_PROPERTIES.items():
        xs = []
        ys = []
        for row in properties[:]:
            xs.append(float(row["X"]))
            ys.append(float(row["Y"]))
        positions[str(planet)] = {"X": xs, "Y": ys}
    # print(positions)

    return positions


def calculate_distances(parsed_data):
    distances = {}  # [MARS: {"Earth": dist_to_earth}, "Jupiter": dist_to_jupit]
    # calculate distances
    for planet, pos in parsed_data.items():
        distances[planet] = {}
        for target_planet in PLANET_IDENTIFIERS:
            if planet == target_planet:
                continue
            distances[planet][target_planet] = []
            # one distance per day
            for day in range(len(pos["X"])):
                p1 = [pos["X"][day], pos["Y"][day]]  # vector
                p2 = [
                    parsed_data[target_planet]["X"][day],
                    parsed_data[target_planet]["Y"][day],
                ]  # vector
                p1p2 = [p2[0] - p1[0], p2[1] - p1[1]]
                dist = math.sqrt(math.pow(p1p2[0], 2) + math.pow(p1p2[1], 2))
                distances[planet][target_planet].append(round(dist, 6))

    # print(distances)
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
                    for i, dist in enumerate(d):
                        writer.writerow([a, b, i, dist])

    f.close()


def calculate_mostest_closest(csvfile):
    try:
        if not csvfile:
            return

        import numpy as np

        names = np.loadtxt(csvfile, delimiter=",", usecols=(0, 1), dtype=str)
        dists = np.loadtxt(csvfile, delimiter=",", usecols=3)

        means = {planet: {} for planet in PLANET_IDENTIFIERS}

        for planet in PLANET_IDENTIFIERS:
            for reversedp in PLANET_IDENTIFIERS.__reversed__():
                if planet == reversedp:
                    break
                mask = (names[:, 0] == planet) & (names[:, 1] == reversedp)
                m = dists[mask].mean()
                means[planet][reversedp] = m
                means[reversedp][planet] = m

        for planet, others in means.items():
            closest = min(others, key=others.get)
            print(
                f"{pstr(planet)} closest to {closest} on average ({others[closest]:.3f} AU)"
            )
    except FileNotFoundError:
        print(
            f"Could not find csv file.\nMake sure to generate one first by running 'python3 {Path(sys.argv[0]).name} csv'"
        )


def pstr(string, pref_width=8):
    pstring = string
    pstring += ":"
    while len(pstring) < pref_width:
        pstring = f"{pstring}" + " "
    return pstring


def print_usage() -> None:
    prog = Path(sys.argv[0]).name
    print(f"""usage: python3 {prog} <command>

commands:
  (none) | help      show this message
  fetch              download ephemeris data from JPL Horizons into data/
  json               calculate distances and write out.json
  csv                calculate distances and write out.csv
  closest <csvfile>  find each planet's closest planet on average""")


def main() -> None:
    argv = sys.argv

    # don't fetch every rerun
    def routine():
        return calculate_distances(parse_data())

    match argv[1:]:
        case []:
            print_usage()

        case ["fetch"]:
            fetch_data()

        case ["json"]:
            generate_json(routine())

        case ["csv"]:
            generate_csv(routine())

        case ["closest", csvfile]:
            calculate_mostest_closest(csvfile)

        case _:
            print_usage()


if __name__ == "__main__":
    main()
