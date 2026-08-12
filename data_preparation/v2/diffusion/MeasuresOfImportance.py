from numpy import argsort, cumsum, sum

def LorenzCenters(potential):
    '''
        Input:
            Potential from grid.
        This function computes the indices of the centers in the linearized grid.
        We are using here the index column and not the double index.
    '''
    # Step 1: Sort the potential and compute the sorting map
    sorted_indices = argsort(potential)
    # Step 2: Compute the cumulative distribution
    sorted_potential = potential[sorted_indices]
    cumulative = cumsum(sorted_potential)
    # Step 3: Determine the angle and delta index
    angle = cumulative[-1] - cumulative[-2]
#    print('angle: ',angle)
    Fstar = int(len(cumulative) +1 -cumulative[-1]/angle)
    # Step 4: Retrieve the indices based on the delta index and mapping
    result_indices = [sorted_indices[-i] for i in range(len(cumulative) - int(Fstar))]
    cumulative = cumulative/sum(sorted_potential)

    return result_indices,angle,cumulative,Fstar
