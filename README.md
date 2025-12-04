# Prismatic Trials Lists
Python tool to list Prismatic Trials for Risk of Rain 2.
Pre-generated lists for every significant update are available.

## Complete Lists
|Game Version| | Release Date | Trial List |
|:---|:---:|:---:|:---:|
|Initial Release|1.0.0.5 -> 1.0.1.1|2020-08-11|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/1.0-Prismatic-Trials.txt)|
|Sundered Grove and Anniversary Updates|1.0.2.0 -> 1.1.1.4|2020-11-03|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/Anniversary-Prismatic-Trials.txt)|
|Survivors of the Void DLC Update|1.2.1.0 -> 1.2.4.4 (SotV)|2022-03-01|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/SotV-Prismatic-Trials.txt)|
|Devotion Update|1.2.4.4 (Devotion)|2024-05-20|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/Devotion-Prismatic-Trials.txt)|
|Seekers of the Storm DLC Update|1.3.1#274 -> 1.3.9#553|2024-08-27|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/SotS-Prismatic-Trials.txt)|
|Alloyed Collective DLC Update|1.4.0#840 -> ...|2025-11-18|[link](https://github.com/verstatx/ror2-trials-list/blob/master/lists/Alloyed-Prismatic-Trials.txt)|

## Script Setup
Requires python 3.7 or higher, and the `looseversion` python library.

On Windows:
```cmd
py -m pip install -r requirements.txt
```

On Linux:
```bash
python -m pip install -r requirements.txt
```

## Script Usage
Run the script through the command line via python:

On Windows:
```cmd
py weeklyrun.py
```

On Linux:
```bash
python weeklyrun.py
```

By default the script outputs the current trial.
The following options are supported:
```
usage: weeklyrun.py [-h] [-v GAME_VERSION] [-d YYYY-MM-DD | -c <32-bit uint> | -s <64-bit uint>] [num_trials]

List Prismatic Trials for Risk of Rain 2

positional arguments:
  num_trials            Number of trials to list. (default: 1)
                        "all" lists every valid trial - 2363 trials in total.

options:
  -h, --help            show this help message and exit
  -v, --version GAME_VERSION
                        Specify game version. (default: alloyed)
                        Supported Options:
                          1.0                 Initial Release                     (1.0.0.5)
                          Anniversary         Anniversary Update                  (1.1.0.1)
                          SotV                Survivors of the Void DLC Update    (1.2.1.0)
                          Devotion            Devotion Update                     (1.2.4.4)
                          SotS                Seekers of the Storm DLC Update     (1.3.1#274)
                          Alloyed             Alloyed Collective DLC Update       (1.4.0#840)
                          <version number>    Any game version in the format 1.2.3.4 or 1.2.3#456
  -d, --date YYYY-MM-DD
                        Start date to generate trials from. (default: now)
                        First trial date is 2018-08-27
  -c, --cycle <32-bit uint>
                        3-day seed cycle to start generating trials from.
                        Allows unreachable, but valid trial seeds.
  -s, --seed <64-bit uint>
                        Override seed generation and print this trial seed.
                        Allows impossible trial seeds.
```

