import sys
import struct
import datetime
from argparse import ArgumentParser, RawTextHelpFormatter
from bisect import bisect
from itertools import chain
from string import digits
from looseversion import LooseVersion


""" Prismatic Trial Constants """

trialEpoch = datetime.date(2018, 8, 27)
Y1970 = datetime.date(1970, 1, 2)
Y2038 = datetime.date(2038, 1, 19)


""" RNG Utils """

UINT64_MASK=0xFFFFFFFFFFFFFFFF
UINT32_MASK=0xFFFFFFFF
FLOAT32_EPSILON_NEGATIVE=5.9604645e-8

def double_to_float(d):
    return struct.unpack("f", (struct.pack("f", d)))[0]

def toFloat01(num):
    num &= UINT32_MASK
    num >>= 8
    num = double_to_float(float(num)) # match C# casting procedure: (float)(double)num
    num *= FLOAT32_EPSILON_NEGATIVE
    return double_to_float(num)

class SplitMix64:
    def __init__(self, seed = 0):
        self.x = seed & UINT64_MASK

    def next(self):
        self.x = (self.x + 0x9e3779b97f4a7c15) & UINT64_MASK
        num = self.x
        num = ((num ^ (num >> 30)) * 0xbf58476d1ce4e5b9) & UINT64_MASK
        num = ((num ^ (num >> 27)) * 0x94d049bb133111eb) & UINT64_MASK
        return (num ^ (num >> 31)) & UINT64_MASK

class Xoroshiro128Plus:
    JUMP = (0xdf900294d8f554a5, 0x170865df4b3201fc)
    LONGJUMP = (0xd2a98b26625eee7b, 0xdddf9b1090aa7ac1)

    def __init__(self, seed = 0):
        self.state = [0, 0]
        self.result = 0
        self.set_seed(seed = seed)
        self.calls = 0

    def set_seed(self, seed = 0):
        initializer = SplitMix64(seed)
        self.result = initializer.x
        self.state[0] = initializer.next()
        self.state[1] = initializer.next()
        self.calls = 0

    def rotl(self, x, k):
        return (x << k | x >> 64 - k) & UINT64_MASK

    def next(self):
        s0 = self.state[0]
        s1 = self.state[1]
        self.result = (s0 + s1) & UINT64_MASK

        s1 ^= s0
        self.state[0] = self.rotl(s0, 24) ^ s1 ^ ((s1 << 16) & UINT64_MASK)
        self.state[1] = self.rotl(s1, 37)
        self.calls += 1

        return self.result

    def jump(self):
        s0 = 0
        s1 = 0

        for i in JUMP:
            for j in range(64):
                if (i & 1 << j):
                    s0 ^= self.state[0]
                    s1 ^= self.state[1]
                self.next()

        self.state[0] = s0
        self.state[1] = s1
        calls += 2**64

    def long_jump(self):
        s0 = 0
        s1 = 1

        for i in LONGJUMP:
            for j in range(64):
                if (i & 1 << j):
                    s0 ^= self.state[0]
                    s1 ^= self.state[1]
                self.next()

        self.state[0] = s0
        self.state[1] = s1
        calls += 2**96

    def calc_req_bits(self, num):
        ret = 0
        while (num):
            num >>= 1
            ret += 1
        return ret

    def range_uint32_uniform(self, max_exclusive):
        if (max_exclusive == 0):
            raise TypeError

        num = 32 - self.calc_req_bits(max_exclusive)

        while True:
            ret = (self.next() & UINT32_MASK) >> num
            if (ret < max_exclusive):
                return ret

    def rangeInt(self, min_inclusive, max_exclusive):
        return min_inclusive + self.range_uint32_uniform(max_exclusive - min_inclusive)


""" Hopoo/Gearbox can't seem to decide how they want to shuffle lists """

def shuffleArray_V1(array, rng):
    for i in range(len(array)):
        rand = rng.rangeInt(0, len(array))
        tmp = array[i]
        array[i] = array[rand]
        array[rand] = tmp

def shuffleArray_V2(array, rng):
    for i in range(len(array)-1, -1, -1):
        rand = rng.rangeInt(0, i+1)
        tmp = array[i]
        array[i] = array[rand]
        array[rand] = tmp

def shuffleArray_V3(array, rng):
    for i in range(len(array)):
        rand = rng.rangeInt(i, len(array))
        tmp = array[i]
        array[i] = array[rand]
        array[rand] = tmp


""" Stage Utils """

class Stage:
    def __init__(self, name, scene_list, base_name=None):
        self.name = name

        if isinstance(scene_list, str):
            self.scenes = [scene_list]
            self.base_name = scene_list
        else:
            self.scenes = list(scene_list)

            # Automatically set base_name (only if scene names start with base name, and end with numeric suffix)
            if base_name is None and all(self.scenes[0].rstrip(digits) == x.rstrip(digits) for x in self.scenes):
                self.base_name = self.scenes[0].rstrip(digits)

    def has_overrides(self):
        return len(self.scenes) > 1

    def has_scene(self, scene_name):
        return scene_name in self.scenes


# Nested List
class SceneCatalogV1:
    def __init__(self, stage_list):
        self._stagePool = stage_list

    # RoR2::Run::PickNextStageScene(SceneDef[])
    def PickNextStageScene(self, nextStageRng, activeScene=None):
        # IsValidNextStage()
        if activeScene is None:
            # Stage 1
            activePool = self._stagePool
        else:
            # Stage 2+
            activePool = [stage for stage in self._stagePool if not stage.has_scene(activeScene)]

        chosenStage = activePool[nextStageRng.rangeInt(0, len(activePool))]
        return chosenStage.name, self._ChooseSceneName(nextStageRng, chosenStage)

    # RoR2::SceneDef::ChooseSceneName()
    def _ChooseSceneName(self, nextStageRng, chosenStage):
        if chosenStage.has_overrides():
            return chosenStage.scenes[nextStageRng.rangeInt(0, len(chosenStage.scenes))]
        else:
            return chosenStage.base_name

# TODO Support for out-of-order scene variant overrides
# Flat List
class SceneCatalogV2:
    def __init__(self, stage_list):
        self._stagePool = stage_list
        self._scenePool = SceneCatalogV2._flatten(stage_list)

    def _flatten(stage_list):
        return [(stage.name, scene) for stage in stage_list for scene in stage.scenes]

    # RoR2::Run::PickNextStageScene(WeightedSelection<SceneDef>)
    def PickNextStageScene(self, nextStageRng, activeScene=None):
        # IsValidNextStage()
        # NOTE: This does not implement the broken stage 1 blacklist introduced around the SotS Update
        # Sky Meadow is intended to be a valid stage from stage 2 onwards,
        # but because the game selects the next stage when the stage 1 exit is activated
        # and the stage counter only increments after the transition to the next stage occurs,
        # the condition checking the number of stages cleared is always one stage behind what was assumed by the code
        # Effectively, Sky Meadow can only appear from stage 3 onward
        if activeScene is None:
            # Stage 1
            activePool = self._scenePool
        else:
            # Stage 2+
            activePool = SceneCatalogV2._flatten([
                stage for stage in self._stagePool if not stage.has_scene(activeScene)
            ])

        return activePool[nextStageRng.rangeInt(0, len(activePool))]


""" Version List Utils """

class VersionVariant:
    MIN=LooseVersion("1.0.0.5")
    MAX=LooseVersion("1.4.0#840")

    def __init__(self, versions_dict):
        # Sort by version (dict sort Python 3.7+)
        self.versions = dict(sorted(versions_dict.items(), key=lambda x: LooseVersion(x[0])))

    def __getitem__(self, key):
        if key in self.versions:
            return self.versions[key]

        # Find highest version released before desired
        keys = list(self.versions.keys())
        index = bisect(keys, LooseVersion(key), key=lambda x: LooseVersion(x))

        if index == 0:
            raise IndexError(f"Unsupported version: \"{key}\"")

        return self.versions[keys[index - 1]]

    def __contains__(self, key):
        return key in self.versions


""" Game Version Definitions """

# FIXME These lists are incomplete, random patches had major changes for PT
startingScenesRandom = VersionVariant({

    # Initial Release
    "1.0.0.5": SceneCatalogV1([
        Stage("Distant Roost",         ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"              ),
        Stage("Wetland Aspect",         "foggyswamp"                  ),
        Stage("Rallypoint Delta",       "frozenwall"                  ),
        Stage("Titanic Plains",        ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                     ),
        Stage("Siren's Call",           "shipgraveyard"               ),
        Stage("Sky Meadow",             "skymeadow"                   ),
        Stage("Scorched Acres",         "wispgraveyard"               ),
    ]),

    # Stadia/Sundered Grove Update
    "1.0.2.0": SceneCatalogV1([
        Stage("Distant Roost",         ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"              ),
        Stage("Wetland Aspect",         "foggyswamp"                  ),
        Stage("Rallypoint Delta",       "frozenwall"                  ),
        Stage("Titanic Plains",        ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                     ),
        Stage("Sundered Grove",         "rootjungle"                  ),
        Stage("Siren's Call",           "shipgraveyard"               ),
        Stage("Sky Meadow",             "skymeadow"                   ),
        Stage("Scorched Acres",         "wispgraveyard"               ),
    ]),

    # Survivors of the Void DLC Update
    "1.2.1.0": SceneCatalogV2([
        Stage("Aphelian Sanctuary",     "ancientloft"                  ),
        Stage("Distant Roost",          ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"               ),
        Stage("Wetland Aspect",         "foggyswamp"                   ),
        Stage("Rallypoint Delta",       "frozenwall"                   ),
        Stage("Titanic Plains",         ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                      ),
        Stage("Sundered Grove",         "rootjungle"                   ),
        Stage("Siren's Call",           "shipgraveyard"                ),
        Stage("Sky Meadow",             "skymeadow"                    ),
        Stage("Siphoned Forest",        "snowyforest"                  ),
        Stage("Sulfur Pools",           "sulfurpools"                  ),
        Stage("Scorched Acres",         "wispgraveyard"                ),
    ]),

    # Devotion Update
    # FIXME There are two 1.2.4.4 versions:
    # The first one is a pre-Devotion patch (Void fields update has Prismatic Trials changes irrelevant to this script)
    # The second one is the actual Devotion update (this is the one targeted here)
    "1.2.4.4": SceneCatalogV2([
        Stage("Aphelian Sanctuary",     "ancientloft"                  ),
        Stage("Distant Roost",          ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"               ),
        Stage("Wetland Aspect",         "foggyswamp"                   ),
        Stage("Rallypoint Delta",       "frozenwall"                   ),
        Stage("Titanic Plains",         ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                      ),
        Stage("Verdant Falls",          "lakes"                        ),
        Stage("Sundered Grove",         "rootjungle"                   ),
        Stage("Siren's Call",           "shipgraveyard"                ),
        Stage("Sky Meadow",             "skymeadow"                    ),
        Stage("Siphoned Forest",        "snowyforest"                  ),
        Stage("Sulfur Pools",           "sulfurpools"                  ),
        Stage("Scorched Acres",         "wispgraveyard"                ),
    ]),

    # Seekers of the Storm DLC Update
    "1.3.1#274": SceneCatalogV2([
        Stage("Aphelian Sanctuary",     "ancientloft"                 ),
        Stage("Distant Roost",         ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"              ),
        Stage("Wetland Aspect",         "foggyswamp"                  ),
        Stage("Rallypoint Delta",       "frozenwall"                  ),
        Stage("Titanic Plains",        ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                     ),
        #Stage("Treeborn Colony",       "habitat"                     ),
        Stage("Golden Dieback",         "habitatfall"                 ),
        #Stage("Helminth Hatchery",     "helminthroost"               ),
        Stage("Verdant Falls",          "lakes"                       ),
        Stage("Viscous Falls",          "lakesnight"                  ),
        Stage("Reformed Altar",         "lemuriantemple"              ),
        Stage("Sundered Grove",         "rootjungle"                  ),
        Stage("Siren's Call",           "shipgraveyard"               ),
        #Stage("Sky Meadow",            "skymeadow"                   ), # Bugged stage 1 blacklist
        Stage("Siphoned Forest",        "snowyforest"                 ),
        Stage("Sulfur Pools",           "sulfurpools"                 ),
        Stage("Shattered Abodes",       "village"                     ),
        Stage("Disturbed Impact",       "villagenight"                ),
        Stage("Scorched Acres",         "wispgraveyard"               ),
    ]),

    # Alloyed Collective DLC Update
    "1.4.0#840": SceneCatalogV2([
        Stage("Aphelian Sanctuary",     "ancientloft"                 ),
        Stage("Distant Roost",         ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"              ),
        Stage("Wetland Aspect",         "foggyswamp"                  ),
        Stage("Rallypoint Delta",       "frozenwall"                  ),
        Stage("Titanic Plains",        ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                     ),
        #Stage("Treeborn Colony",       "habitat"                     ),
        Stage("Golden Dieback",         "habitatfall"                 ),
        #Stage("Helminth Hatchery",     "helminthroost"               ),
        Stage("Iron Alluvium",          "ironalluvium"                ),
        Stage("Iron Auroras",           "ironalluvium2"               ),
        Stage("Verdant Falls",          "lakes"                       ),
        Stage("Viscous Falls",          "lakesnight"                  ),
        Stage("Reformed Altar",         "lemuriantemple"              ),
        Stage("Pretender's Precipice",  "nest"                        ),
        Stage("Repurposed Crater",      "repurposedcrater"            ),
        Stage("Sundered Grove",         "rootjungle"                  ),
        Stage("Siren's Call",           "shipgraveyard"               ),
        #Stage("Sky Meadow",            "skymeadow"                   ), # Bugged stage 1 blacklist
        Stage("Siphoned Forest",        "snowyforest"                 ),
        Stage("Sulfur Pools",           "sulfurpools"                 ),
        Stage("Shattered Abodes",       "village"                     ),
        Stage("Disturbed Impact",       "villagenight"                ),
        Stage("Scorched Acres",         "wispgraveyard"               ),
    ]),

    # Hallowed Concepts DLC Update
    "1.5.0#1210": SceneCatalogV2([
        Stage("Aphelian Sanctuary",     "ancientloft"                 ),
        Stage("Distant Roost",         ["blackbeach", "blackbeach2"]  ),
        Stage("Abyssal Depths",         "dampcavesimple"              ),
        Stage("Wetland Aspect",         "foggyswamp"                  ),
        Stage("Rallypoint Delta",       "frozenwall"                  ),
        Stage("Damp Caverns",           "fungal"                      ),
        Stage("Titanic Plains",        ["golemplains", "golemplains2"]),
        Stage("Abandoned Aqueduct",     "goolake"                     ),
        #Stage("Treeborn Colony",       "habitat"                     ),
        Stage("Golden Dieback",         "habitatfall"                 ),
        #Stage("Helminth Hatchery",     "helminthroost"               ),
        Stage("Iron Alluvium",          "ironalluvium"                ),
        Stage("Iron Auroras",           "ironalluvium2"               ),
        Stage("Verdant Falls",          "lakes"                       ),
        Stage("Viscous Falls",          "lakesnight"                  ),
        Stage("Reformed Altar",         "lemuriantemple"              ),
        Stage("Tenebrous Quagmire",     "mire"                        ),
        Stage("Pretender's Precipice",  "nest"                        ),
        Stage("Repurposed Crater",      "repurposedcrater"            ),
        Stage("Sundered Grove",         "rootjungle"                  ),
        Stage("Lurid Basilica",         "sanctum"                     ),
        Stage("Siren's Call",           "shipgraveyard"               ),
        #Stage("Sky Meadow",            "skymeadow"                   ), # Bugged stage 1 blacklist
        Stage("Siphoned Forest",        "snowyforest"                 ),
        Stage("Sulfur Pools",           "sulfurpools"                 ),
        Stage("Shattered Abodes",       "village"                     ),
        Stage("Disturbed Impact",       "villagenight"                ),
        Stage("Scorched Acres",         "wispgraveyard"               ),
    ]),
})

artifactCatalog = VersionVariant({

    # Initial Release
    "1.0.0.5": [
        "Spite",
        "Command",
        "Honor",
        "Enigma",
        "Chaos",
        "Glass",
        "Dissonance",
        "Evolution",
        "Metamorphosis",
        "Sacrifice",
        "Vengeance",
        "Kin",
        "Swarms",
        "Death",
        "Frality",
        "Soul"
    ],

    # SotV
    "1.2.1.0": [
        "Spite",
        "Command",
        "Honor",
        "Enigma",
        "Chaos",
        "Glass",
        "Dissonance",
        "Evolution",
        "Metamorphosis",
        "Sacrifice",
        "Vengeance",
        "Kin",
        "Swarms",
        "Death",
        "Frality",
        "Soul"
    ],

    # Devotion
    "1.2.4.4": [
        "Spite",
        "Command",
        "Delusion",
        "Devotion",
        "Honor",
        "Enigma",
        "Chaos",
        "Glass",
        "Dissonance",
        "Evolution",
        "Metamorphosis",
        "Sacrifice",
        "Vengeance",
        "Kin",
        "Swarms",
        "Death",
        "Frality",
        "Soul"
    ],

    # SotS
    "1.3.1#274": [
        "Spite",
        "Command",
        "Delusion",
        "Devotion",
        "Honor",
        "Enigma",
        "Chaos",
        "Glass",
        "Dissonance",
        "Evolution",
        "Metamorphosis",
        "Rebirth",
        "Sacrifice",
        "Vengeance",
        "Kin",
        "Swarms",
        "Death",
        "Frality",
        "Soul"
    ],

    # Alloyed
    "1.4.0#840": [
        "Spite",
        "Command",
        "Delusion",
        "Devotion",
        "Honor",
        "Enigma",
        "Chaos",
        "Glass",
        "Dissonance",
        "Evolution",
        "Prestige",
        "Metamorphosis",
        "Rebirth",
        "Sacrifice",
        "Vengeance",
        "Kin",
        "Swarms",
        "Death",
        "Frality",
        "Soul"
    ],
})

shuffleArray = VersionVariant({

    # Initial Release
    "1.0.0.5": shuffleArray_V1,

    # SotV
    "1.2.1.0": shuffleArray_V2,

    # Alloyed
    "1.4.0#840": shuffleArray_V3,
})


""" Argument Parsing """

versionAlias = {
    "1.0":          "1.0.0.5", # 1.0.0.5 -> 1.0.1.1
    "sundered":     "1.0.2.0", # 1.0.2.0 -> 1.0.3.1
    "anniversary":  "1.1.0.1", # 1.1.0.1 -> 1.1.1.4
    "anniv":        "1.1.0.1",
    "sotv":         "1.2.1.0", # 1.2.1.0 -> 1.2.4.4 (SotV)
    "void":         "1.2.1.0",
    "devotion":     "1.2.4.4", # 1.2.4.4 (Devotion)
    "sots":         "1.3.1#274", # 1.3.1#274 -> 1.3.9#553
    "seekers":      "1.3.1#274",
    "alloyed":      "1.4.0#840", # 1.4.0#840 -> 1.4.1#912
    "hallowed":     "1.5.0#1210", # 1.5.0#1210 -> ...
}

versionDescriptions = {
    "1.0": "Initial Release",
    "Anniversary": "Anniversary Update", # TODO untested; same as Sundered Grove update
    "SotV": "Survivors of the Void DLC Update",
    "Devotion": "Devotion Update",
    "SotS": "Seekers of the Storm DLC Update",
    "Alloyed": "Alloyed Collective DLC Update",
    "Hallowed": "Hallowed Concepts DLC Update",
    "<version number>": "Any game version in the format 1.2.3.4 or 1.2.3#456"
}

printVDesc = "\n".join(
    "  {:20}{:36}{}"
    .format(v, d, "".join(str(f"({versionAlias[i]})") for i in [v.lower()] if v.lower() in versionAlias))
    for v, d in versionDescriptions.items()
)

def parse_version_opt(user_version):
    if user_version.lower() in versionAlias:
        return versionAlias[user_version.lower()]

    target_version = LooseVersion(user_version)
    if target_version < VersionVariant.MIN:
        print(
            f"error: Unsupported game version. Minimum supported version is {VersionVariant.MIN}\n",
            file=sys.stderr
        )

        raise TypeError

    if target_version > VersionVariant.MAX:
        print(
            f"warning: Generating Trials for newer game version. Maximum supported version is {VersionVariant.MAX}\n",
            file=sys.stderr
        )

        #raise TypeError

    return user_version

def parse_date_opt(user_date):
    if user_date == "now":
        return datetime.datetime.now(datetime.timezone.utc).date() # Today

    trial_date = datetime.datetime.fromisoformat(user_date)

    return trial_date.astimezone(datetime.timezone.utc).date()

def parse_cycle_opt(user_cycle):
    return int(user_cycle, base=0) & UINT32_MASK

def parse_seed_opt(user_seed):
    return int(user_seed, base=0) & UINT64_MASK

def parse_num_trials_opt(user_num_trials):
    if user_num_trials.lower() == "all":
        return "all"

    return int(user_num_trials)


program_description = "List Prismatic Trials for Risk of Rain 2"
ap = ArgumentParser(description=program_description, formatter_class=RawTextHelpFormatter)

# Number of trials
num_help = """\
Number of trials to list. (default: %(default)s)
\"all\" lists every valid trial - 2363 trials in total.
"""
ap.add_argument(
    "num_trials", nargs='?',
    type=parse_num_trials_opt, default=1, help=num_help)

# Game Version
version_help = """\
Specify game version. (default: %(default)s)
Supported Options:
"""
version_help += printVDesc
version_default = list(versionAlias.keys())[-1]
ap.add_argument(
    "-v", "--version", metavar="GAME_VERSION",
    type=parse_version_opt, default=version_default, help=version_help
)


start_group = ap.add_mutually_exclusive_group()

# Start Date (xor group)
date_help = f"""\
Start date to generate trials from. (default: %(default)s)
First trial date is {trialEpoch}\
"""
start_group.add_argument(
    "-d", "--date", metavar="YYYY-MM-DD",
    type=parse_date_opt, default="now", help=date_help
)

# Start Cycle (xor group)
cycle_help = """\
3-day seed cycle to start generating trials from.
Allows unreachable, but valid trial seeds.\
"""
start_group.add_argument(
    "-c", "--cycle", metavar="<32-bit uint>",
    type=parse_cycle_opt, help=cycle_help
)

# Exact Seed (xor group)
seed_help = """\
Override seed generation and print this trial seed.
Allows impossible trial seeds.\
"""
start_group.add_argument(
    "-s", "--seed", metavar="<64-bit uint>",
    type=parse_seed_opt, help=seed_help
)


args = ap.parse_args()

num_trials = args.num_trials
game_version = args.version
current_trial = args.date
start_cycle = args.cycle
user_seed = args.seed


""" Prismatic Trial Logic and Program Output """

# Determine operation mode and range
if start_cycle is None:
    start_cycle = ((current_trial - trialEpoch) / 3).days

if num_trials == "all":
    num_cycles = ((Y2038 - trialEpoch) / 3).days + 1 # cycles 0 -> 2361
    frozen_cycle = ((Y1970 - trialEpoch) / 3).days # cycle -5923
    trials_range = chain(range(0, num_cycles), [frozen_cycle])
else:
    trials_range = range(start_cycle, start_cycle+num_trials)

if user_seed is not None:
    trials_range = range(1)

# Output state control
first_trial=True # For blank line separator
suppress_date=False

# Generate trial seeds
for seedcycle in trials_range:
    if not first_trial:
        print()
    else:
        first_trial = False

    if user_seed is not None:
        # override seed generation (prints one trial)
        seed = user_seed
        if seed & UINT32_MASK == 0:
            # realistic seed
            seedcycle=(seed >> 32) & UINT32_MASK
        else:
            # impossible seed
            suppress_date=True
    else:
        # regular seed generation (proceeds normally)
        seed = (seedcycle & UINT32_MASK) << 32

    # Determine trial date if possible
    try:
        trialDate = trialEpoch + datetime.timedelta(seedcycle*3)
        localDate = datetime.datetime.combine(trialDate, datetime.time(), datetime.timezone.utc)\
                    .astimezone(None)
    except:
        trialDate, localDate = ["N/A"]*2

    if suppress_date:
        # overriden seed
        seedcycle, trialDate, localDate = ["N/A"]*3

    # Output trial Metadata
    print("Trial Date: {}, Local Date: {}".format(trialDate, localDate))
    print("Seed cycle:", seedcycle)
    print("Weekly run seed:", seed)

    # Simulate RNG to determine basic trial details

    # Determine artifact list
    artifactRNG = Xoroshiro128Plus(seed)
    if (toFloat01(artifactRNG.next()) < 1.0): # Does nothing, but advances the RNG anyway
        num = artifactRNG.rangeInt(2, 7)

        shuffledArtifacts = artifactCatalog[game_version].copy()
        shuffleArray[game_version](shuffledArtifacts, artifactRNG)

        print(
            "Enabled artifact of",
            ", ".join(shuffledArtifacts[i] for i in range(num) if shuffledArtifacts[i] != "Metamorphosis")
        )

    # Determine stage list
    runRNG = Xoroshiro128Plus(seed)
    nextStageRng = Xoroshiro128Plus(runRNG.next())
    stageRngGenerator = Xoroshiro128Plus(runRNG.next())

    # RoR2::Run::GenerateStageRNG()
    stageRng = Xoroshiro128Plus(stageRngGenerator.next())
    stageRng.next() # bossRewardRng
    stageRng.next() # treasureRng
    stageRng.next() # spawnRng
    stageRng.next() # randomSurvivorOnRespawnRng

    print("Stage 1: ", end="")
    stageName, sceneName = startingScenesRandom[game_version].PickNextStageScene(nextStageRng)
    print(f"{stageName} ({sceneName})")

    print("Stage 2: ", end="")
    stageName, sceneName = startingScenesRandom[game_version].PickNextStageScene(nextStageRng, sceneName)
    print(f"{stageName} ({sceneName})")

    #bossAffixRng = Xoroshiro128Plus(runRNG.next())

    print(end='', flush=True)

