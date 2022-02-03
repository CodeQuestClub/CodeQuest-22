import math
import random
from codequest22.server.events import *
from codequest22.server.requests import *
from codequest22 import stats
from heapq import heappop, heappush

from codequest22.stats.ants import Fighter

# TODO
# Similar idea to defended for settlers - or something more fast evolving
# That being said, in a 4 person game you can't dominate. So maybe do streaks? (Test this)
# Move to current closest settle spot
# Fighter ants go to patrol mode once at point.

DEBUG = True

def get_team_name():
    return f"Jackson"

def get_team_image():
    return "test_bots/img/hello.png"

my_index = None
def read_index(player_index, num_players):
    global my_index, defeated
    my_index = player_index
    for x in range(num_players, 4):
        defeated[x] = True

map_data = {}
spawns = {}
production = []
production_info = {}
defended = {}
occupied = {}
last_occupied = {}
distance = {}
interesting_path_map = {}
defeated = [False]*4
interesting_points = []
reset_points = []
allocated = []
my_energy = stats.general.STARTING_ENERGY
cur_tick = 0

def read_map(md, energy_info):
    global map_data, spawn, production, distance, defended, occupied, production_info, interesting_path_map, interesting_points, reset_points
    map_data = md
    for y in range(len(map_data)):
        for x in range(len(map_data[0])):
            if map_data[y][x] == "F":
                production.append((x, y))
                allocated.append(0)
                interesting_points.append((x, y))
            if map_data[y][x] in "RBYG":
                spawns["RBYG".index(map_data[y][x])] = (x, y)
                occupied["RBYG".index(map_data[y][x])] = []
                reset_points.append((x, y))
            if map_data[y][x] == "Z":
                # TODO: This can probably be made better
                interesting_points.append((x, y))
    for key in occupied:
        occupied[key] = {key2: False for key2 in production}
        last_occupied[key] = {key2: -10000 for key2 in production}
        interesting_path_map[key] = {}
    production_info = {
        key2: {
            "base": energy_info[key2],
            "mult": 1
        }
        for key2 in production
    }
    defended = {
        key: {
            key2: 0
            for key2 in production
        }
        for key in occupied 
    }
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

class Ant:
    def __init__(self, type, ticks, hp, position, energy) -> None:
        self.ant_type = type
        self.ticks = ticks
        self.hp = hp
        self.position = position
        self.energy = energy
        self.previous_positions = []

ants = [{} for _ in range(4)]
ant_ids = 0
total_ants = 0
current_workers = 0
current_settlers = 0

def calculate_defended():
    # Calculates whether certain production zones are defended, or at least safe for me to move to.
    for player_index in occupied:
        for prod in production:
            defended[player_index][prod] = 0
    for player_index in occupied:
        for key in ants[player_index]:
            if player_index == my_index:
                if ants[player_index][key].cur_allocation in production:
                    if ants[player_index][key].ant_type == AntTypes.FIGHTER:
                        defended[player_index][ants[player_index][key].cur_allocation] += 1
                    else:
                        # My own workers don't mean shit for defence, or taking away my enemies energy.
                        defended[player_index][ants[player_index][key].cur_allocation] += 0
                continue
            # Are we close enough to the particular production site?
            pos = ants[player_index][key].position
            ipos = (round(pos[0]), round(pos[1]))
            for prod in production:
                d = abs(pos[0] - prod[0]) + abs(pos[1] - prod[1])
                if d < 3:
                    if ants[player_index][key].ant_type == AntTypes.FIGHTER:
                        defended[player_index][prod] += 1
                    else:
                        defended[player_index][prod] += 0.2
                    break
            else:
                options = interesting_path_map[player_index].get(ipos, {})
                options = list(sorted([(v, k) for k, v in options.items()]))[-3::]
                for _, option in options:
                    if option in production:
                        if ants[player_index][key].ant_type == AntTypes.FIGHTER:
                            defended[player_index][option] += 1 / len(options)
                        else:
                            defended[player_index][option] += 0.2 / len(options)

def calculate_production_benefit():
    global production_info
    for prod in production:
        loop_cost = stats.ants.Worker.COST / stats.ants.Worker.TRIPS
        loop_return = production_info[prod]["base"] * production_info[prod]["mult"]
        d = distance[prod][spawns[my_index]]
        enemy_d = 1000000
        for other in occupied:
            if other == my_index or defeated[other]: continue
            enemy_d = min(enemy_d, distance[prod][spawns[other]])
        loop_time = d / stats.ants.Worker.SPEED + d / (stats.ants.Worker.SPEED * stats.ants.Worker.ENCUMBERED_RATE)
        rpt = (loop_return - loop_cost) / loop_time
        total_allocation = loop_time * (stats.energy.PER_TICK / stats.energy.DELAY)
        production_info[prod]["rpt"] = rpt
        production_info[prod]["allocation"] = math.floor(total_allocation)
        score_diff = 0
        if d < enemy_d:
            score_diff = pow(enemy_d / d, 3)
        elif d > enemy_d:
            score_diff = -pow(d / enemy_d, 3)
        production_info[prod]["score"] = rpt + score_diff

def allocate_production_zone(ant):
    global allocated
    choices = []
    for i, p in enumerate(production):
        bad = False
        # TODO
        for index in defended:
            if index != my_index and defended[index][p]:
                bad = True
        if bad and not defended[my_index][p]:
            # Don't go somewhere being actively defended by others.
            continue
        rpt = production_info[p]["rpt"]
        allocation_max = production_info[p]["allocation"]
        score = production_info[p]["score"]
        choices.append((allocation_max <= allocated[i], -score, p, i))
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

current_settled = []
settle_timer = 0

def spawn_excluding_settler_action(max_amount=stats.general.MAX_SPAWNS_PER_TICK):
    global current_workers, total_ants, ant_ids, my_energy
    spawn_requests = []
    # Only production is worthwhile. So just decide if I need to defend anything
    options = []
    for prod in production:
        options.append((production_info[prod]["score"], production_info[prod]["allocation"], prod))
    options.sort()
    options = options[::-1]
    remaining_workers = current_workers
    remaining_cost = my_energy
    remaining_spawns = max_amount
    # First option is best for return and has the highest allocation.
    for score, allocate, prod in options:
        if remaining_workers <= 0 and remaining_cost <= 0:
            break
        if remaining_spawns <= 0:
            break
        n_defending = defended[my_index][prod]
        for index in defended:
            if index == my_index: continue
            n_defending -= defended[index][prod]
        if n_defending < 0 and (remaining_cost > stats.ants.Worker.COST * 5 or remaining_workers >= 5):
            # We need to spawn a fighter to secure this production area - We'll have multiple ants coming soon.
            if remaining_cost >= stats.ants.Fighter.COST and total_ants < stats.general.MAX_ANTS_PER_PLAYER - 5 and remaining_workers + remaining_spawns >= 5:
                key = f"Fighter-{ant_ids}"
                ant = Ant(AntTypes.FIGHTER, stats.ants.Fighter.LIFESPAN, stats.ants.Fighter.HP, spawns[my_index], stats.ants.Fighter.COST)
                ant.cur_allocation = prod
                ants[my_index][key] = ant
                spawn_requests.append(SpawnRequest(AntTypes.FIGHTER, id=f"Fighter-{ant_ids}", goal=prod))
                ant_ids += 1
                total_ants += 1
                remaining_cost -= stats.ants.Fighter.COST
                remaining_spawns -= 1
                defended[my_index][prod] += 1
        # Now we should allocate as many workers as possible
        if remaining_workers < allocate:
            max_spawn = min(allocate - remaining_workers, remaining_spawns)
            max_spawn = min(max_spawn, remaining_cost // stats.ants.Worker.COST)
            max_spawn = max(0, max_spawn)
            max_spawn = min(max_spawn, stats.general.MAX_ANTS_PER_PLAYER - total_ants)
            for i in range(max_spawn):
                key = f"Worker-{ant_ids}"
                ant = Ant(AntTypes.WORKER, 100000, stats.ants.Worker.HP, spawns[my_index], stats.ants.Worker.COST)
                ant.cur_allocation = prod
                allocated[production.index(prod)] += 1
                ants[my_index][key] = ant
                spawn_requests.append(SpawnRequest(AntTypes.WORKER, id=key, goal=prod))
                ant_ids += 1
                total_ants += 1
                remaining_cost -= stats.ants.Worker.COST
                remaining_spawns -= 1
            remaining_workers += max_spawn
            current_workers += max_spawn
        remaining_workers -= allocate
    my_energy = remaining_cost
    return spawn_requests

def handle_events(events):
    global ants, ant_ids, my_energy, current_settled, settle_timer, total_ants, cur_tick, current_workers, current_settlers, defended, defeated
    cur_tick += 1
    settle_timer -= 1
    for l in ants:
        for k in l:
            l[k].ticks -= 1
    req = []
    glob_to_remove = []
    for ev in events:
        if isinstance(ev, DieEvent):
            if ev.player_index == my_index:
                total_ants -= 1
                ant = ants[my_index][ev.ant_id]
                if ant.cur_allocation in production and ant.ant_type == AntTypes.WORKER:
                    allocated[production.index(ant.cur_allocation)] -= 1
                    ant.cur_allocation = None
                if ant.ant_type == AntTypes.WORKER:
                    current_workers -= 1
                if ant.ant_type == AntTypes.FIGHTER:
                    pass
                if ant.ant_type == AntTypes.SETTLER:
                    current_settlers -= 1
            glob_to_remove.append((ev.player_index, ev.ant_id))
    for ev in events:
        if isinstance(ev, SpawnEvent):
            # Create the relavent object.
            if ev.player_index != my_index:
                # Otherwise, we do this on request.
                ants[ev.player_index][ev.ant_id] = Ant(ev.ant_type, getattr(ev, "ticks_left", 1000000), ev.hp, ev.position, ev.cost)
        elif isinstance(ev, MoveEvent):
            pindex, key, pos = ev.player_index, ev.ant_id, ev.position
            ipos = (round(ants[pindex][key].position[0]), round(ants[pindex][key].position[1]))
            ants[pindex][key].previous_positions.append(ipos)
            ants[pindex][key].position = pos
            for x, y in reset_points:
                d = abs(x - pos[0]) + abs(y - pos[1])
                if d < 1:
                    ants[pindex][key].previous_positions = []
            for x, y in interesting_points:
                d = abs(x - pos[0]) + abs(y - pos[1])
                if d < 1.5:
                    # We passed by interesting point.
                    for (a, b), (e, f) in zip(ants[pindex][key].previous_positions, ants[pindex][key].previous_positions[1:] + [(x, y)]):
                        # Get all points between a,b and e,f.
                        d = abs(a-e) + abs(b-f)
                        max_d = 2 * math.ceil(d)
                        for z in range(0, max_d):
                            point0 = a + z / max_d * (e-a) / abs(e-a) if e != a else a
                            point1 = b + z / max_d * (f-b) / abs(f-b) if f != b else b
                            point = (round(point0), round(point1))
                            if point not in interesting_path_map[pindex]:
                                interesting_path_map[pindex][point] = {}
                            interesting_path_map[pindex][point][(x, y)] = cur_tick
            if ants[pindex][key].ant_type == AntTypes.FIGHTER:
                # Check if last_occupied needs to be updated
                for prod in production:
                    d = abs(prod[0] - pos[0]) + abs(prod[1] - pos[1])
                    if d < 5:
                        last_occupied[pindex][prod] = cur_tick
        elif isinstance(ev, ProductionEvent):
            if ev.player_index == my_index:
                req.append(GoalRequest(ev.ant_id, spawns[my_index]))
                ant = ants[my_index][ev.ant_id]
                if ant.cur_allocation in production:
                    allocated[production.index(ant.cur_allocation)] -= 1
                    ant.cur_allocation = None
        elif isinstance(ev, DepositEvent):
            if ev.player_index == my_index:
                req.append(GoalRequest(ev.ant_id, allocate_production_zone(ants[ev.player_index][ev.ant_id])))
                my_energy += ev.energy_amount
        elif isinstance(ev, ZoneActiveEvent):
            current_settled = ev.points
            settle_timer = ev.num_ticks
            for ant in ants[my_index].values():
                if ant.ant_type == AntTypes.SETTLER:
                    req.append(GoalRequest(ant.ant_id, current_settled[0]))
        elif isinstance(ev, ZoneDeactivateEvent):
            current_settled = []
        elif isinstance(ev, FoodTileActiveEvent):
            production_info[ev.pos]["mult"] = ev.multiplier
        elif isinstance(ev, FoodTileDeactivateEvent):
            production_info[ev.pos]["mult"] = 1
        elif isinstance(ev, TeamDefeatedEvent):
            defeated[ev.defeated_index] = True
    for pi, ai in glob_to_remove:
        del ants[pi][ai]
    for pindex in occupied:
        if pindex == my_index: continue
        for key in ants[pindex]:
            a, b = round(ants[pindex][key].position[0]), round(ants[pindex][key].position[1])
    # print("NEW TICK")
    # for key in defended:
    #     for pos in defended[key]:
    #         if defended[key][pos] > 0:
    #             print(f"Defense {key} {pos} = {defended[key][pos]}")
    # Start responding with spawns and fighter movement.
    calculate_defended()
    calculate_production_benefit()
    # Tug of war between 4 options:
    # * Worker spawns
    # * Settler spawns
    # * Fighter spawns
    # * Holding onto energy
    # For now, holding onto energy is useless provided you funnel enough into worker production.
    # Fighter spawns and worker/settler disputes boils down to deciding which parts of the map you want under control.
    # As a rule, at least 20 workers should be alive, otherwise let's just spam workers.
    if current_settled == [] or current_workers < 30:
        req.extend(spawn_excluding_settler_action())
    else:
        # 1. Evaluate distance to settle zone, and how many current fighters.
        my_d = distance[spawns[my_index]][tuple(current_settled[0])]
        # TODO: Evaluate if we'll have enough time to get score.
        other_info = []
        for idx in occupied:
            if idx == my_index or defeated[idx]: continue
            their_d = distance[spawns[idx]][tuple(current_settled[0])]
            fighters_on_zone = 0
            for key in ants[idx]:
                if ants[idx][key].ant_type != AntTypes.FIGHTER: continue
                ipos = (round(ants[idx][key].position[0]), round(ants[idx][key].position[1]))
                options = interesting_path_map[idx].get(ipos, {})
                options = list(sorted([(v, k) for k, v in options.items()]))[-3::]
                for _, option in options:
                    if option in current_settled:
                        fighters_on_zone += 1/len(options)
            other_info.append((their_d/my_d, fighters_on_zone))
        my_fighters = 0
        for key in ants[my_index]:
            if ants[my_index][key].ant_type == AntTypes.FIGHTER:
                if ants[my_index][key].cur_allocation in current_settled:
                    my_fighters += 1
        # I know how far away each player is, and how many fighters they are sending.
        # Is it worth fighting for?
        other_info.sort(key=lambda i: (i[1], i[0]))
        other_info = other_info[::-1]
        # If there are less than 8 fighters at zone then automatically go for it.
        good = False
        if other_info[0][1] < 8:
            good = True
        # If we have more than a 1/3 of all current fighters moving towards then also go.
        elif sum(map(lambda x: x[1], other_info)) < 3 * my_fighters:
            good = True
        if good:
            # Allocate max 80% fighters/settlers to hit the ratio, then do the worker stuff for rest.
            maximum_spawns = round(stats.general.MAX_SPAWNS_PER_TICK*0.8)
            total_spawns = 0
            while total_spawns < maximum_spawns:
                if total_ants >= stats.general.MAX_ANTS_PER_PLAYER: break
                if my_energy < max(stats.ants.Settler.COST, stats.ants.Fighter.COST): break
                if my_fighters > 0 and current_settlers / my_fighters < 0.3:
                    key = f"Settler-{ant_ids}"
                    ant = Ant(AntTypes.SETTLER, stats.ants.Settler.LIFESPAN, stats.ants.Settler.HP, spawns[my_index], stats.ants.Settler.COST)
                    ant.ant_id = key
                    ant.cur_allocation = current_settled[0]
                    ants[my_index][key] = ant
                    req.append(SpawnRequest(AntTypes.SETTLER, id=key, goal=current_settled[0]))
                    current_settlers += 1
                    ant_ids += 1
                    total_ants += 1
                    total_spawns += 1
                    my_energy -= stats.ants.Settler.COST
                else:
                    key = f"Fighter-{ant_ids}"
                    ant = Ant(AntTypes.FIGHTER, stats.ants.Fighter.LIFESPAN, stats.ants.Fighter.HP, spawns[my_index], stats.ants.Fighter.COST)
                    ant.ant_id = key
                    ant.cur_allocation = current_settled[0]
                    ants[my_index][key] = ant
                    req.append(SpawnRequest(AntTypes.FIGHTER, id=key, goal=current_settled[0]))
                    my_fighters += 1
                    ant_ids += 1
                    total_ants += 1
                    total_spawns += 1
                    my_energy -= stats.ants.Fighter.COST
            # Only spawn more workers if we don't want to spawn more settlers/fighters.
            if current_workers < 40:
                req.extend(spawn_excluding_settler_action(max_amount=stats.general.MAX_SPAWNS_PER_TICK - total_spawns))
        else:
            req.extend(spawn_excluding_settler_action())

    return req
