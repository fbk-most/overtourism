"""
    The player is an object that:
        - is uniquely classified
        - interacts with the environment (other players at different times and different sub-spaces)
        - is characterized by utility functions that can be coupled among themselves and the environment in complicated ways
        - has a state that can be updated by the environment
    FACTS OF MODEL:
        - will of the player is determined by the utility function (that depends on a set of parameters)
        - rationality 

"""
import torch
from typing import List, Dict
import numpy as np
from utility_function import *
from pydantic import BaseModel,Field

class Player(BaseModel):
    """
        user_id: int in [0, N_users-1]
        user_type: str in {`COMMUTER`,`INHABITANT`,`TOURIST`,`VISITOR`}
        v_utility: np.ndarray of shape (N_places,) representing the utility of each place for the user
    """
    name: str = Field(...,description="unique identification of the user")
    
    def __init__(self, 
                 user_id: int,
                 user_type: str,
                 v_utility: np.ndarray,
                 v_state: np.ndarray,
                 final_destination: int,
                 str_utility_function:str,      # The utility function that the user applies to choose.
                 temperature: float = 1.0,
                 time_wait: int = None,
                 past_choices: np.ndarray = None,
                 Herfindahl_index: float = None,
                 ):
        assert np.shape(v_state) == np.shape(v_utility), "v_state and v_utility must have the same shape"
        self.user_id = user_id                              # There are different classes that correspond to different kind of users (COMMUTERS,...)
        self.user_type = user_type
        self.v_utility = v_utility
        self.v_state = v_state
        self.temperature = temperature
        self.final_destination = final_destination          # The destination comes from the environment we put them.        
        self.time_wait = time_wait
        self.past_choices = past_choices
        self.Herfindahl_index = Herfindahl_index            # sum_ v_state^2 [1/N -> max entropy, 1 -> just one place] 
        self.str_utility_function = str_utility_function    # The utility function that the user applies to choose.

    def update_utility(self,model,is_memory):
        """
        Update the utility of the player based on the current state and the model's predictions.
        """
        with torch.no_grad():
            # Get the current state as a tensor
            current_state = torch.tensor(self.v_state, dtype=torch.float32).unsqueeze(0)
            # Get the model's prediction for the current state
            predicted_utility = model(current_state).squeeze().numpy()
            # Update the player's utility
            self.v_utility = predicted_utility
            if is_memory:
                if self.past_choices is None:
                    self.past_choices = np.array([self.v_state])
                else:
                    self.past_choices = np.vstack([self.past_choices, self.v_state])
                # Update Herfindahl index
                self.Herfindahl_index = np.sum(self.v_state**2) / (np.sum(self.v_state)**2)
            else:
                self.past_choices = None
                self.Herfindahl_index = None
    def choose_next_location(self):
        """
        Choose the next location based on the utility function and the current state.
        """
        if self.str_utility_function == "softmax":
            probabilities = softmax(self.v_utility / self.temperature)
            next_location = np.random.choice(len(self.v_utility), p=probabilities)
        elif self.str_utility_function == "epsilon_greedy":
            next_location = epsilon_greedy(self.v_utility, epsilon=self.temperature)
        elif self.str_utility_function == "herfindahl":
            next_location = herfindahl_choice(self.v_utility, self.v_state, self.Herfindahl_index)
        else:
            raise ValueError(f"Unknown utility function: {self.str_utility_function}")
        return next_location