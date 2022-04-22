from abc import ABC
from codequest22.server.ant import Ant, WorkerAnt
import codequest22.stats as stats

class Event(ABC):
    
    def __repr__(self) -> str:
        return f"{{\"{self.__class__.__name__}\": {self.get_args()}}}"
    
    def to_json(self):
        return {
            "classname": self.__class__.__name__,
            "args": self.get_args(),
        }
    
    @classmethod
    def from_json(cls, data):
        return cls(*data["args"])

class SpawnEvent(Event):
    """
    An event that means an ant has been spawned.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * ant_type: The type of ant spawned. Is one of AntTypes
    * position: The spawn position of the ant
    * hp: The starting hp of the ant
    * cost: The energy cost incurred by the player
    """
    def __init__(self, ant: Ant, cost: int, color=None, path=None, goal=None) -> None:
        self.ant_str = ant.to_json()
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.ant_type = ant.TYPE
        self.position = ant.position[::-1]
        self.hp = ant.hp
        self.cost = cost
        self.color = color
        self.path = path
        self.goal = goal
        if hasattr(ant, "ticks_left"):
            self.ticks_left = ant.ticks_left
        if hasattr(ant, "remaining_trips"):
            self.remaining_trips = ant.remaining_trips

    def get_args(self):
        return [self.ant_str, self.cost, self.color, self.path, self.goal]

class MoveEvent(Event):
    """
    An event that means an ant has moved in the last tick.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * position: The current position of the ant
    """
    def __init__(self, ant: Ant, path=None) -> None:
        self.ant_str = ant.to_json()
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.position = ant.position[::-1]
        self.path = path

    def get_args(self):
        return [self.ant_str, self.path]

class DieEvent(Event):
    """
    An event that means an ant has died in the last tick.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * old_age: True if the ant died of end of lifespan, and False if killed by losing hp
    """
    def __init__(self, ant: Ant) -> None:
        self.ant_str = ant.to_json()
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.old_age = ant.hp > 0
    
    def get_args(self):
        return [self.ant_str]

class AttackEvent(Event):
    """
    An event that means an ant has been attacked by another ant.
    Attributes:
    * attacker_index: The index of the player the attacker ant was spawned from (0-3)
    * defender_index: The index of the player the defender ant was spawned from (0-3)
    * attacker_id: The particular id assigned to the attacker ant
    * defender_id: The particular id assigned to the defender ant
    * defender_hp: The new hp of the defending ant
    """
    def __init__(self, ant1: Ant, ant2: Ant) -> None:
        self.ant1_str = ant1.to_json()
        self.ant2_str = ant2.to_json()
        self.attacker_index = ant1.player_index
        self.defender_index = ant2.player_index
        self.attacker_id = ant1.id
        self.defender_id = ant2.id
        self.defender_hp = ant2.hp

    def get_args(self):
        return [self.ant1_str, self.ant2_str]

class DepositEvent(Event):
    """
    An event that means a worker ant has deposited it's held energy to the queen.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * cur_energy: The old energy level of the player
    * energy_amount: The amount of energy deposited by the ant
    * total_energy: The new energy level of the player
    """
    def __init__(self, ant: WorkerAnt, cur_energy: int) -> None:
        self.ant_str = ant.to_json()
        self.cur_energy = cur_energy
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.energy_amount = int(ant.encumbered_energy)
        self.total_energy = min(cur_energy + self.energy_amount, stats.general.MAX_ENERGY_STORED)

    def get_args(self):
        return [self.ant_str, self.cur_energy]

class ProductionEvent(Event):
    """
    An event that means an ant has been given energy by the food tile.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * energy_amount: The amount of energy the ant has received
    """
    def __init__(self, ant: WorkerAnt) -> None:
        self.ant_str = ant.to_json()
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.energy_amount = ant.encumbered_energy
    
    def get_args(self):
        return [self.ant_str]

class ZoneActiveEvent(Event):
    """
    An event that means a settler zone is now active.
    Attributes:
    * points: A list of all points in this settler zone
    * num_ticks: The number of ticks this zone will remain active
    """
    def __init__(self, zone_index: int, num_ticks: int, points: list) -> None:
        self.zone_index = zone_index
        self.points = [tuple(p) for p in points]
        self.num_ticks = num_ticks

    def get_args(self):
        return [self.zone_index, self.num_ticks, self.points]

class ZoneDeactivateEvent(Event):
    """
    An event that means a settler zone is no longer active.
    Attributes:
    * points: A list of all points in this settler zone
    """
    def __init__(self, zone_index: int, points: list) -> None:
        self.zone_index = zone_index
        self.points = [tuple(p) for p in points]

    def get_args(self):
        return [self.zone_index, self.points]

class FoodTileActiveEvent(Event):
    """
    An event that means a food tile is now supercharged.
    Attributes:
    * pos: The position of the food tile
    * num_ticks: The number of ticks the food tile will remain supercharged
    * multiplier: The multiplier applied to all energy received from this tile. Currently always 2.
    """
    def __init__(self, pos: tuple, num_ticks: int, multiplier: int) -> None:
        self.pos = tuple(pos)
        self.num_ticks = num_ticks
        self.multiplier = multiplier

    def get_args(self):
        return [self.pos, self.num_ticks, self.multiplier]

class FoodTileDeactivateEvent(Event):
    """
    An event that means a food tile is no longer supercharged
    Attributes:
    * pos: The position of the food tile
    """
    def __init__(self, pos: tuple) -> None:
        self.pos = pos

    def get_args(self):
        return [self.pos]

class SettlerScoreEvent(Event):
    """
    An event that means a settler ant has received hill score for sitting on an active hill zone.
    Attributes:
    * player_index: The index of the player this ant was spawned from (0-3)
    * ant_id: The particular id assigned to this ant
    * score_amount: The amount of score the player has received for this action
    """
    def __init__(self, ant: Ant, score: int) -> None:
        self.ant_str = ant.to_json()
        self.player_index = ant.player_index
        self.ant_id = ant.id
        self.score_amount = score

    def get_args(self):
        return [self.ant_str, self.score_amount]

class QueenAttackEvent(Event):
    """
    An event that means a fighter ant has successfully attacked the queen
    Attributes:
    * ant_player_index: The index of the player whose fighter ant is attacking (0-3)
    * queen_player_index: The index of the player whose queen is being attacked (0-3)
    * ant_id: The particular id assigned to the fighter ant
    * queen_hp: The new queen hp
    """
    def __init__(self, ant: Ant, queen_index: int, queen_hp: int):
        self.ant_str = ant.to_json()
        self.ant_player_index = ant.player_index
        self.ant_id = ant.id
        self.queen_player_index = queen_index
        self.queen_hp = queen_hp

    def get_args(self):
        return [self.ant_str, self.queen_player_index, self.queen_hp]

class TeamDefeatedEvent(Event):
    """
    An event that means a particular queen has lost all of its health and the team are defeated.
    Attributes:
    * defeated_index: The index of the player who was defeated (0-3)
    * by_index: The index of the player who defeated them (0-3)
    * new_hill_score: The new hill score of the player who defeated them
    """
    def __init__(self, defeated_index: int, by_index: int, hill_score: int) -> None:
        self.defeated_index = defeated_index
        self.by_index = by_index
        self.new_hill_score = hill_score

    def get_args(self):
        return [self.defeated_index, self.by_index, self.new_hill_score]
