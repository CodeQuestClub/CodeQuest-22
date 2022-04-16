#!/usr/bin/python3
""" Top-level file for MolarFox's bot, Codequest beta 2022! """

""" Project Serial MOLPRO D-1437006"""

import logging
import random
from collections import namedtuple
from dataclasses import dataclass, field
from typing import List, Dict

import codequest22.server.events as cq_events
# Temp import paths for local testing
import codequest22.stats as stats
from codequest22.server.ant import Ant, WorkerAnt, FighterAnt, SettlerAnt, AntTypes
from codequest22.server.requests import Request, GoalRequest, SpawnRequest

# import codequest22.stats as stats
# from codequest22.server.ant import Ant, AntTypes
# from codequest22.server.events import Event, DepositEvent, DieEvent, ProductionEvent
# from codequest22.server.requests import Request, GoalRequest, SpawnRequest

LOG_LEVEL = logging.INFO
LOG = logging.getLogger("bot.MolarFox")
LOG.setLevel(LOG_LEVEL)

# TODO: Add to feedback - send Ant instantiated object in events, rather than json dict (or include method to go back to class instance easily)
ant_name_to_cls = {
    "WorkerAnt": AntTypes.WORKER,
    "FighterAnt": AntTypes.FIGHTER,
    "SettlerAnt": AntTypes.SETTLER
}

# --- PRECONFIG ----------------------------------------------
BotParams = namedtuple(
    'BotParams',
    [
        "energy_select_jitter",
        "min_reserve_ants",
        "worker_settler_ratio"
    ]
)

@dataclass
class MapInfo:
    total_players: int = 0
    queen_loc: tuple = (0, 0)
    map: List[List[str]] = field(default_factory=list)
    queen_dist_map: Dict[tuple, int] = field(default_factory=dict)
    spawn_locs: List[tuple] = field(default_factory=list)
    food_locs: List[tuple] = field(default_factory=list)
    hill_locs: List[tuple] = field(default_factory=list)
    hill_index_loc: Dict[int, tuple] = field(default_factory=dict)
    energy_info: Dict[tuple, int] = field(default_factory=dict)
    food_overcharges: Dict[tuple, int] = field(default_factory=dict)
    active_hills: Dict[tuple, bool] = field(default_factory=dict)

@dataclass
class BotState:
    params: BotParams
    energy: int = stats.general.STARTING_ENERGY
    total_ants: int = 0
    ant_counts: Dict[Ant, int] = field(default_factory=dict)
    player_index: int = 0
    tgt_energy_zones: List[tuple] = field(default_factory=list)
    groupings: List[Ant] = field(default_factory=list)
    map_info: MapInfo = field(default_factory=MapInfo)

# vvv Bot runtime params to be defined below vvv
BOT_STATE = BotState(
    params=BotParams(
        energy_select_jitter=3,
        min_reserve_ants=1,
        worker_settler_ratio=(3, 1)
    )
)


# --- CORE METHODS ------------------------------------------- 
def get_team_name() -> str:
    return "MolarFox"

def read_index(player_index, n_players) -> None:
    BOT_STATE.player_index = player_index
    BOT_STATE.map_info.total_players = n_players


def read_map(md, energy_info):
    BOT_STATE.map_info.map = md
    BOT_STATE.map_info.energy_info = energy_info
    compute_djikstra()
    LOG.info({"message": "Map preprocessed successfully!"})


def handle_failed_requests(failed_req_list) -> None:
    # Looks like we can snoop on all the failed requests, even ones from other players :eyes:
    for req in failed_req_list:
        if req.player_index == BOT_STATE.player_index:
            # TODO: Try and gracefully handle some failed requests, esp. spawn reqs
            LOG.error({
                "message": "A request was rejected by the tournament runner",
                "request": req,
                "bot-state": BOT_STATE
            })
            raise ValueError()


def handle_events(event_list: List[cq_events.Event]) -> List[Request]:
    out_reqs: List[Request] = []

    # # Determine target energy zone(s) - potential yield from site div distance from queen
    food_scores = list(sorted([  # yield / dist
        ((10*BOT_STATE.map_info.food_overcharges.get(f_loc, 1) / BOT_STATE.map_info.queen_dist_map[f_loc]), f_loc)
        for f_loc in BOT_STATE.map_info.food_locs
    ]))
    # food_tgts = [x for x in food_scores if food_scores[0][0] - x[0] < BOT_STATE.params.energy_select_jitter]

    food_tgts = food_scores[-3:]

    # Extremely hacky temp code
    # food_tgts = [(5, list(sorted(BOT_STATE.map_info.food_locs, key=lambda x: BOT_STATE.map_info.queen_dist_map[x]))[0])]

    # Determine target hill
    for hill, state in BOT_STATE.map_info.active_hills.items():
        if state:
            hill_tgt = hill
    else:
        hill_tgt = None


    for event in event_list:
        if isinstance(event, cq_events.SpawnEvent):
            pass    # TODO: owo, counterintelligence

        elif isinstance(event, cq_events.MoveEvent):
            pass

        elif isinstance(event, cq_events.DieEvent):
            # TODO: Feedback - make interface easier to use / pass object instance w/ event
            if event.player_index == BOT_STATE.player_index:
                BOT_STATE.ant_counts[ant_name_to_cls.get(event.ant_str["classname"])] -= 1
                BOT_STATE.total_ants -= 1

        elif isinstance(event, cq_events.AttackEvent):
            pass

        elif isinstance(event, cq_events.DepositEvent):
            if event.player_index == BOT_STATE.player_index:
                out_reqs.append(GoalRequest(event.ant_id, random.choice(food_tgts)[1]))
                BOT_STATE.energy = event.cur_energy

        elif isinstance(event, cq_events.ProductionEvent):
            if event.player_index == BOT_STATE.player_index:
                out_reqs.append(GoalRequest(event.ant_id, BOT_STATE.map_info.queen_loc))

        elif isinstance(event, cq_events.ZoneActiveEvent):
            # No idea where to collect zone_index per hill corresponding to what this event provides
            # In djikstras below, assuming that the traversal order corresponds to this indexing
            # TODO: Add to feedback doc
            BOT_STATE.map_info.active_hills[
                BOT_STATE.map_info.hill_index_loc[event.zone_index]
            ] = True

        elif isinstance(event, cq_events.ZoneDeactivateEvent):
            BOT_STATE.map_info.active_hills[
                BOT_STATE.map_info.hill_index_loc[event.zone_index]
            ] = False

        elif isinstance(event, cq_events.FoodTileActiveEvent):
            BOT_STATE.map_info.food_overcharges[event.pos] = event.multiplier

        elif isinstance(event, cq_events.FoodTileDeactivateEvent):
            BOT_STATE.map_info.food_overcharges[event.pos] = 1

        elif isinstance(event, cq_events.SettlerScoreEvent):
            pass

        elif isinstance(event, cq_events.QueenAttackEvent):
            if event.queen_player_index == BOT_STATE.player_index:
                pass    # TODO: Deploy reserve troops to defend

        elif isinstance(event, cq_events.TeamDefeatedEvent):
            pass

        else:
            LOG.error({
                "message": "Unknown event received",
                "event": event,
                "bot_state": BOT_STATE
            })

        """ TODO: Edge cases
                - Worker ant stuck waiting at food source too long
        """

        # Spawn and send
        spawned_this_tick = 0
        while (
            spawned_this_tick < stats.general.MAX_SPAWNS_PER_TICK and   # Spawn ratelimit check
            BOT_STATE.total_ants < stats.general.MAX_ANTS_PER_PLAYER - BOT_STATE.params.min_reserve_ants and    # Max ants check
            (
                BOT_STATE.energy - (BOT_STATE.params.min_reserve_ants * stats.ants.Fighter.COST) > stats.ants.Worker.COST or
                (BOT_STATE.energy - (BOT_STATE.params.min_reserve_ants * stats.ants.Fighter.COST) > stats.ants.Settler.COST and hill_tgt)
            )
        ):
            # Spawn settlers if there is an active hill, maintain settler to worker ratio
            # if hill_tgt and percentage_settlers() < ideal_settler_ratio():
            if hill_tgt:
                out_reqs.append(req_spawn_ant(AntTypes.SETTLER, hill_tgt))
                BOT_STATE.energy -= stats.ants.Settler.COST
                spawned_this_tick += 1
            else:
                out_reqs.append(req_spawn_ant(AntTypes.WORKER, random.choice(food_tgts)[1]))
                BOT_STATE.energy -= stats.ants.Worker.COST
                spawned_this_tick += 1

    return out_reqs


# --- AUX METHODS --------------------------------------------
# TODO: move aux methods out to modular imports
def compute_djikstra():
    """Taken verbatim from sample bot code"""
    BOT_STATE.map_info.spawn_locs = [(0,0) for _ in range(4)]
    hill_index = 0  # Assuming that the hill index above corresponds to this traversal order (?)
    for y in range(len(BOT_STATE.map_info.map)):
        for x in range(len(BOT_STATE.map_info.map[0])):
            if BOT_STATE.map_info.map[y][x] == "F":
                BOT_STATE.map_info.food_locs.append((x, y))
            elif BOT_STATE.map_info.map[y][x] == "Z":
                BOT_STATE.map_info.hill_locs.append((x, y))
                BOT_STATE.map_info.hill_index_loc[hill_index] = (x, y)
                hill_index += 1
            elif BOT_STATE.map_info.map[y][x] in "RBYG":
                BOT_STATE.map_info.spawn_locs["RBYG".index(BOT_STATE.map_info.map[y][x])] = (x, y)
    # Read map is called after read_index
    BOT_STATE.map_info.queen_loc = BOT_STATE.map_info.spawn_locs[BOT_STATE.player_index]
    # Dijkstra's Algorithm: Find the shortest path from your spawn to each food zone.
    # Step 1: Generate edges - for this we will just use orthogonally connected cells.
    adj = {}
    h, w = len(BOT_STATE.map_info.map), len(BOT_STATE.map_info.map[0])
    # A list of all points in the grid
    points = []
    # Mapping every point to a number
    idx = {}
    counter = 0
    for y in range(h):
        for x in range(w):
            adj[(x, y)] = []
            if BOT_STATE.map_info.map[y][x] == "W": continue
            points.append((x, y))
            idx[(x, y)] = counter
            counter += 1
    for x, y in points:
        for a, b in [(y+1, x), (y-1, x), (y, x+1), (y, x-1)]:
            if 0 <= a < h and 0 <= b < w and BOT_STATE.map_info.map[a][b] != "W":
                adj[(x, y)].append((b, a, 1))
    # Step 2: Run Dijkstra's
    import heapq
    # What nodes have we already looked at?
    expanded = [False] * len(points)
    # What nodes are we currently looking at?
    queue = []
    # What is the distance to the startpoint from every other point?
    heapq.heappush(queue, (0, BOT_STATE.map_info.queen_loc))
    while queue:
        d, (a, b) = heapq.heappop(queue)
        if expanded[idx[(a, b)]]: continue
        # If we haven't already looked at this point, put it in expanded and update the distance.
        expanded[idx[(a, b)]] = True
        BOT_STATE.map_info.queen_dist_map[(a, b)] = d
        # Look at all neighbours
        for j, k, d2 in adj[(a, b)]:
            if not expanded[idx[(j, k)]]:
                heapq.heappush(queue, (
                    d + d2,
                    (j, k)
                ))


def req_spawn_ant(ant_type: Ant, goal: tuple) -> SpawnRequest:
    BOT_STATE.ant_counts[ant_type] = BOT_STATE.ant_counts.get(ant_type, 0) + 1
    BOT_STATE.total_ants += 1
    return SpawnRequest(ant_type, goal=goal, id=None, color=None)


def percentage_settlers() -> float:
    return BOT_STATE.ant_counts[AntTypes.SETTLER] / (BOT_STATE.ant_counts[AntTypes.WORKER] + BOT_STATE.ant_counts[AntTypes.SETTLER])


def ideal_settler_ratio() -> float:
    return BOT_STATE.params.worker_settler_ratio[1] / sum(BOT_STATE.params.worker_settler_ratio)
