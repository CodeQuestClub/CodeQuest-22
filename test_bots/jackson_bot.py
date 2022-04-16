import math
import random
from codequest22.server.events import *
from codequest22.server.requests import *
from codequest22.server.ant import AntTypes
from codequest22 import stats
from heapq import heappop, heappush

DEBUG = True

def get_team_name():
    return f"Jackson"

my_index = None
def read_index(player_index, n_players):
    global my_index
    my_index = player_index

map_data = {}
spawns = {}
production = []
distance = {}
allocated = []
my_energy = stats.general.STARTING_ENERGY

def read_map(md, energy_info):
    global map_data, spawn, production, distance
    map_data = md
    for y in range(len(map_data)):
        for x in range(len(map_data[0])):
            if map_data[y][x] == "F":
                production.append((x, y))
                allocated.append(0)
            if map_data[y][x] in "RBYG":
                spawns["RBYG".index(map_data[y][x])] = (x, y)
    # Dijkstra's for every start point.
    # Generate edges
    adj = {}
    h, w = len(map_data), len(map_data[0])
    points = []
    for y in range(h):
        for x in range(w):
            distance[(x, y)] = {}
            adj[(x, y)] = []
            if map_data[y][x] == "W": continue
            points.append((x, y))
    for x, y in points:
        for a, b in [(y+1, x), (y-1, x), (y, x+1), (y, x-1)]:
            if 0 <= a < h and 0 <= b < w and map_data[a][b] != "W":
                adj[(x, y)].append((b, a, 1))
        for a, b in [(y+1, x+1), (y+1, x-1), (y-1, x+1), (y-1, x-1)]:
            if (
                0 <= a < h and 0 <= b < w and 
                map_data[a][b] != "W" and
                map_data[a][x] != "W" and
                map_data[y][b] != "W"
            ):
                adj[(x, y)].append((b, a, math.sqrt(2)))
    idx = {p: i for i, p in enumerate(points)}
    for x, y in points:
        # Dijkstra run
        expanded = [False] * len(points)
        queue = []
        heappush(queue, (0, (x, y)))
        while queue:
            d, (a, b) = heappop(queue)
            if expanded[idx[(a, b)]]: continue
            expanded[idx[(a, b)]] = True
            distance[(x, y)][(a, b)] = d
            # Look at all neighbours
            for j, k, d2 in adj[(a, b)]:
                if not expanded[idx[(j, k)]]:
                    heappush(queue, (
                        d + d2,
                        (j, k)
                    ))

ants = [{} for _ in range(4)]
ant_ids = 0
total_ants = 0

def allocate_production_zone(ant: Ant):
    global allocated
    ipos = (round(ant.position[0]), round(ant.position[1]))
    choices = []
    for i, p in enumerate(production):
        d1 = distance[ipos][p]
        d2 = distance[p][spawns[my_index]]
        if d1 / ant.move_speed + d2 / (ant.move_speed * 0.3) > ant.ticks:
            pass
        allocation_max = d2 / ant.move_speed * (stats.energy.PER_TICK / stats.energy.DELAY)
        choices.append((allocation_max <= allocated[i], d1 + d2, p, i))
    choices.sort()
    if len(choices) == 0:
        return spawns[my_index]
    allocated[choices[0][3]] += 1
    ant.cur_allocation = choices[0][2]
    return choices[0][2]

def handle_failed_requests(requests):
    global my_energy
    for req in requests:
        if req.player_index == my_index:
            print(f"Request {req.__class__.__name__} failed. Reason: {req.reason}.")
            if DEBUG:
                # Raise an error immediately. Something went wrong!
                raise ValueError()
            if isinstance(req, SpawnRequest):
                my_energy += req.cost

def handle_events_worker_trail(events):
    global ants, ant_ids, total_ants
    req = []
    for ev in events:
        if isinstance(ev, SpawnEvent):
            ant_obj = AntTypes.get_class(ev.ant_type)(ev.player_index, ev.ant_id, ev.position, (0, 0, 0))
            ants[ant_obj.player_index][ant_obj.id] = ant_obj
        elif isinstance(ev, MoveEvent):
            pindex, key, pos = ev.player_index, ev.ant_id, ev.position
            ants[pindex][key].position = pos
        elif isinstance(ev, ProductionEvent):
            if ev.player_index == my_index:
                req.append(GoalRequest(ev.ant_id, spawns[my_index]))
        elif isinstance(ev, DepositEvent):
            if ev.player_index == my_index:
                req.append(GoalRequest(ev.ant_id, random.choice(production)))
        elif isinstance(ev, DieEvent):
            pass
    req.append(SpawnRequest(
        ant_type=AntTypes.WORKER, 
        id=f"bleep-bloop-{ant_ids}",
        color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        goal=random.choice(production)
    ))
    ant_ids += 1
    return req

class Ant:
    def __init__(self, type, ticks, hp, id, position) -> None:
        self.type = type
        self.ticks = ticks
        self.hp = hp
        self.ant_id = id
        self.position = position
        self.move_speed = 3 if type == AntTypes.WORKER else (
            1.5 if type == AntTypes.SETTLER else 2
        )
        self.cur_allocation = None

current_settled = []
settle_timer = 0

def handle_events(events):
    global ants, ant_ids, my_energy, current_settled, settle_timer, total_ants
    settle_timer -= 1
    for l in ants:
        for k in l:
            l[k].ticks -= 1
    req = []
    for ev in events:
        if isinstance(ev, DieEvent):
            if ev.player_index == my_index:
                total_ants -= 1
                ant = ants[my_index][ev.ant_id]
                if ant.cur_allocation in production:
                    allocated[production.index(ant.cur_allocation)] -= 1
                    ant.cur_allocation = None
            del ants[ev.player_index][ev.ant_id]
    for ev in events:
        if isinstance(ev, SpawnEvent):
            # Create the relavent object.
            if ev.player_index != my_index:
                # Otherwise, we do this on request.
                ants[ev.player_index][ev.ant_id] = Ant(ev.ant_type, getattr(ev, "ticks_left", 1000000), ev.hp, ev.ant_id, ev.position)
            else:
                total_ants += 1
        elif isinstance(ev, MoveEvent):
            pindex, key, pos = ev.player_index, ev.ant_id, ev.position
            if key not in ants[pindex]: continue
            ants[pindex][key].position = pos
        elif isinstance(ev, ProductionEvent):
            if ev.player_index == my_index:
                if ev.ant_id not in ants[ev.player_index]: continue
                req.append(GoalRequest(ev.ant_id, spawns[my_index]))
                ant = ants[my_index][ev.ant_id]
                if ant.cur_allocation in production:
                    allocated[production.index(ant.cur_allocation)] -= 1
                    ant.cur_allocation = None
        elif isinstance(ev, DepositEvent):
            if ev.player_index == my_index:
                if ev.ant_id not in ants[ev.player_index]: continue
                req.append(GoalRequest(ev.ant_id, allocate_production_zone(ants[ev.player_index][ev.ant_id])))
                my_energy += ev.energy_amount
        elif isinstance(ev, ZoneActiveEvent):
            current_settled = ev.points
            settle_timer = ev.num_ticks
            for ant in ants[my_index].values():
                if ant.type == AntTypes.SETTLER:
                    req.append(GoalRequest(ant.ant_id, current_settled[0]))
        elif isinstance(ev, ZoneDeactivateEvent):
            current_settled = []
    # Is it worth spawning a settler?
    possible_spawns = stats.general.MAX_ANTS_PER_PLAYER - total_ants
    if current_settled != [] and my_energy >= stats.ants.Settler.COST and possible_spawns > 0:
        m, z = min((distance[spawns[my_index]][z], z) for z in current_settled)
        if m < (min(40, settle_timer)-10) * 1.5:
            # Worth spawning - we get 10 ticks in the zone.
            ant = Ant(AntTypes.SETTLER, 40, 10, f"Settler-{ant_ids}", spawns[my_index])
            ants[my_index][ant.ant_id] = ant
            req.append(SpawnRequest(AntTypes.SETTLER, ant.ant_id, goal=z))
            ant_ids += 1
            my_energy -= stats.ants.Settler.COST
            possible_spawns -= 1

    # Let's spawn as many ants as I can, allowing for a settler purchase.
    my_spawns = (my_energy - stats.ants.Settler.COST) // stats.ants.Worker.COST
    my_spawns = max(0, min(my_spawns, possible_spawns))//2
    new_ants = [
        Ant(AntTypes.WORKER, 80, 5, f"Worker-{ant_ids+a}", spawns[my_index])
        for a in range(my_spawns)
    ]
    for ant in new_ants:
        ants[my_index][ant.ant_id] = ant
    req.extend([
        SpawnRequest(AntTypes.WORKER, f"Worker-{ant_ids+a}", goal=allocate_production_zone(new_ants[a]))
        for a in range(my_spawns)
    ])
    ant_ids += my_spawns
    my_energy -= sum(r.cost for r in req if isinstance(r, SpawnRequest) and r.ant_type == AntTypes.WORKER)
    return req
