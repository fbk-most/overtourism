"""
    The arena is the class that contains both the players and the environment.
    

"""
from Player import *
class Arena(BaseModel):
    """
        Arena is the environment a set of multiple players live.
    """
    players: list[Player] = Field(...,description= "list of players ")
    str_name2player: Dict[str, Player] = Field(...,description="dictionary that maps the name of the player to the player object")
