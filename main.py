from dataclasses import dataclass
import math
import sys
from pathlib import Path

import requests


# generic vector class
@dataclass
class Vec3[T]:
    x: T
    y: T
    z: T


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
    print("[Info] Fetching Horizons data...")
    outdir = outdir or Path(__file__).parent / "data"
    outdir.mkdir(parents=True, exist_ok=True)

    failed: list[str] = []
    for planet, identifier in PLANET_IDENTIFIERS.items():
        try:
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
                timeout=60,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[Error] Could not fetch {planet}: {e}")
            failed.append(planet)
            continue

        # Horizons reports query errors with HTTP 200 and no ephemeris block
        if "$$SOE" not in resp.text:
            print(f"[Error] Horizons returned no data for {planet}:\n{resp.text}")
            failed.append(planet)
            continue

        data_file = outdir / f"{planet}.txt"
        print(f"Fetch {pstr(planet)} {data_file}")
        data_file.write_text(resp.text)

    if failed:
        print(f"[Error] Failed to fetch: {', '.join(failed)}")
        sys.exit(1)


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
    positions: dict[str, dict[str, float]] = {}  # {"planet": {"X": xpos, "Y": ypos}}

    datadir = Path(datadir)
    if not datadir.exists():
        raise FileNotFoundError(datadir)

    for planet in PLANET_IDENTIFIERS:
        contents = (datadir / f"{planet}.txt").read_text()
        body = contents.split("$$SOE")[1].split("$$EOE")[0].strip()

        PLANET_PROPERTIES[planet] = [
            dict(zip(_ENTRY_ORDER, (field.strip() for field in line.split(","))))
            for line in body.splitlines()
            if line.strip()
        ]

    # carve out only needed data (x, y and z vectors per planet)
    for planet, properties in PLANET_PROPERTIES.items():
        ps = Vec3([], [], [])
        for row in properties[:]:
            ps.x.append(float(row["X"]))
            ps.y.append(float(row["Y"]))
            ps.z.append(float(row["Z"]))
        positions[str(planet)] = {"X": ps.x, "Y": ps.y, "Z": ps.z}

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
                p1 = Vec3(pos["X"][day], pos["Y"][day], pos["Z"][day])
                p2 = Vec3(
                    parsed_data[target_planet]["X"][day],
                    parsed_data[target_planet]["Y"][day],
                    parsed_data[target_planet]["Z"][day],
                )
                dist = math.dist((p1.x, p1.y, p1.z), (p2.x, p2.y, p2.z))
                distances[planet][target_planet].append(round(dist, 12))

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
            f"[Error] Could not find csv file. Make sure to generate one first by running 'python3 {Path(sys.argv[0]).name} csv'"
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
