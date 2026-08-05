from common_imports import *
class Parameter(BaseModel):
    """
        The parameter is a mathematical structure that encodes the parameters of the utility function.
    """
    name: str = Field(..., description="The name of the parameter")
    value: Any = Field(..., description="The value of the parameter")
    description: str = Field("", description="A description of the parameter")
    
    def __init__(self, name: str, value: Any, description: str = ""):
        super().__init__(name=name, value=value, description=description)


class ParameterSet(BaseModel):    
    """
        The parameter set is a mathematical structure that encodes the parameters of the utility function.
    """
    parameters: Dict[str, Parameter] = Field(..., description="A dictionary that maps the name of the parameter to the parameter object")
    def __init__(self, parameters: Dict[str, Parameter]):
        super().__init__(parameters=parameters)

# I would like the state to be either bosonic (that can take values in the real/complex line) or fermionic (that can take values in {0,1}).
# The fermionic and bosonic states are realizations of state.
# The shape of the state ->
class State(BaseModel):
    """
    The state is a mathematical structure that encodes information that both the environment and the player can use.
    """
    vector_state: Union[np.ndarray, torch.Tensor, jnp.ndarray] = Field(
        ..., description="The state of the environment represented as a vector"
    )
    

    @field_validator("vector_state")
    def validate_vector_state(cls, value):
        if isinstance(value, (np.ndarray, torch.Tensor, jnp.ndarray)):
            return value
        raise ValueError("vector_state must be a numpy.ndarray, torch.Tensor, or jax.numpy.ndarray")

class BosonicState(State):
    """
        The bosonic state is a state that can take values in the real/complex line.
    """
    pass


class FermionicState(State):
    """
        The fermionic state is a state that can take values in {0,1}.
    """
    pass
