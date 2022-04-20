from abc import ABC
from codequest22.server.ant import AntTypes

class Request(ABC):
    
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

class SpawnRequest(Request):
    """
    A request to spawn an ant.
    Arguments:
    * ant_type: One of AntTypes.WORKER, AntTypes.SETTLER and AntTypes.FIGHTER
    * id: An id to give the ant. If it is None, then the game will auto allocate one.
    * color: A color for debugging the ant in game (Currently not functional due to some visual bugs)
    * goal: The goal of this ant to move to. Given as tuple of coordinates.
    """
    def __init__(self, ant_type: AntTypes, id=None, color=None, goal=None) -> None:
        super().__init__()
        self.ant_type = ant_type
        self.id = id
        self.color = color
        self.goal = None
        if goal is not None:
            self.goal = goal[1], goal[0]
        self.cost = AntTypes.get_stats(self.ant_type).COST
    
    def get_args(self):
        return [self.ant_type, self.id, self.color, self.goal]

class GoalRequest(Request):
    """
    A request to change the goal of an ant.
    Arguments:
    * id: The id of the ant to move.
    * position: The position the ant should move towards. Given as tuple of coordinates.
    """
    def __init__(self, id, position) -> None:
        super().__init__()
        self.ant_id = id
        self.position = position

    def get_args(self):
        return [self.ant_id, self.position]

