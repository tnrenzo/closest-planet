# closest-planet

## Overview

This script:
1. Fetches heliocentric positions for all 8 planets, from 2023-02-25 to 2187-12-01.
2. Calculates the distance between every pair of planets for every day (in the ecliptic plane, X/Y only).
3. Averages those distances and finds each planet's closest neighbour.

## Usage

```sh
pip install -r requirements.txt

python3 main.py fetch               # download data into data/
python3 main.py csv                 # write all daily distances to out.csv
python3 main.py closest out.csv     # find each planet's closest planet on average

# optional
python3 main.py json                # write all daily distances to out.json
```

Run `python3 main.py help` for all commands.


<details>
<summary>Show results (Spoilers)</summary>

| Planet  | Closest on average | Mean distance (AU) |
|---------|--------------------|--------------------|
| Mercury | Venus              | 0.778              |
| Venus   | Mercury            | 0.778              |
| Earth   | Mercury            | 1.038              |
| Mars    | Mercury            | 1.558              |
| Jupiter | Mercury            | 5.215              |
| Saturn  | Mercury            | 9.526              |
| Uranus  | Mercury            | 19.200             |
| Neptune | Mercury            | 30.068             |

</details>
