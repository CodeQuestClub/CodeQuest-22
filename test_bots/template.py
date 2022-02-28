from codequest22.server.ant import AntTypes
import codequest22.stats as stats
from codequest22.server.events import *
from codequest22.server.requests import *


def get_team_name() -> str:
    """Returns the name of your team as a short string."""
    return "???"

def get_team_image() -> str:
    """Returns the relative path of your team's banner image. Shown in the game interface."""
    return "placeholder.png"

def read_index(player_index: int, n_players: int) -> None:
    """
    Reads the total number of players and your index within that list.
    n_players: The total number of players
    player_index: Your index of players, starting at 0.

    For example, player_index==2 and n_players==4 means there are 4 players and you are player 3.
    """
    pass

def read_map(map_data: list[list[str]], energy_info: dict[tuple[int, int], int]) -> None:
    """
    Read map data before starting the game.
    map_data: A 2D list of characters, each representing tiles on the board.
        F: Food
        RBYG: Red/Blue/Yellow/Green Queen Ant/Spawn
        W: Wall
        .: Ground
        Z: Hill zone
        map_data[0][0] is the top-left of the field, and map_data[0][-1] is the bottom-left.
    energy_info: A map from food tile coordinates to energy values. For example:
    {
        (4, 6): 30,
        (2, 4): 15
    }
    """
    pass


def handle_failed_requests(requests: list[Request]) -> None:
    """
    Handle failed requests that your or other teams have made.
    Each request has:
        req.player_index: The index of the player who made this request.
        req.reason: A string explaining why the request failed.
    """
    pass

def handle_events(events: list[Event]) -> list[Request]:
    """
    Handle all incoming events and return a list of requests for your ants.
    The full list of possible events is available at codequest22.server.events
    A similar list is available for requests at codequest22.server.requests
    """
    return []
