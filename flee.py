import random
import numpy as np
import sys

class SimulationSettings:
  Softening = 0.0
  #TurnBackAllowed = True # feature disabled for now.
  AgentLogLevel = 0 # set to 1 for basic agent information.
  CampLogLevel = 0  # set to 1 to obtain average times for agents to reach camps at any time step (aggregate info). 
  InitLogLevel  = 0 # set to 1 for basic information on locations added and conflict zones assigned.
  TakeRefugeesFromPopulation = True

  CampWeight = 2.0 # attraction factor for camps.
  ConflictWeight = 0.25 # reduction factor for refugees entering conflict zones.
  MinMoveSpeed = 25 # least number of km that we expect refugees to traverse per time step.
  MaxMoveSpeed = 250 # most number of km that we expect refugees to traverse per time step.
  #UseDynamicCampWeights = True # overrides CampWeight depending on characteristics of the ecosystem.
  CapacityBuffer = 1.0

  AwarenessLevel = 1 #0 = road only, 1 = location, 2 = neighbours, 3 = region.
  UseDynamicAwareness = False # Refugees become smarter over time.

class Person:
  def __init__(self, location):
    self.health = 1

    self.injured = 0

    self.age = 35
    self.location = location
    self.home_location = location
    self.location.numAgents += 1
    self.timesteps_since_departure = 0

    # Set to true when an agent resides on a link.
    self.travelling = False
    
    # Tracks how much distance a Person has been able to travel on the current link.
    self.distance_travelled_on_link = 0

    #if not SimulationSettings.TurnBackAllowed:
    #  self.last_location = None

    if SimulationSettings.AgentLogLevel > 0:
      self.distance_travelled = 0
      self.places_travelled = 1

  def evolve(self):

    if self.travelling == False:
      movechance = self.location.movechance
      outcome = random.random()
      if outcome < movechance:
        # determine here which route to take?
        chosenRoute = self.selectRoute()

        # if there is a viable route to a different location.
        if chosenRoute >= 0:
          # update location to link endpoint
          self.location.numAgents -= 1
          self.location = self.location.links[chosenRoute]
          self.location.numAgents += 1
          self.travelling = True
          self.distance_travelled_on_link = 0

    self.timesteps_since_departure += 1


  def finish_travel(self, distance_moved_this_timestep=0):
    if self.travelling:

      # update last location of agent.
      #if not SimulationSettings.TurnBackAllowed:
      #  self.last_location = self.location

      self.distance_travelled_on_link += SimulationSettings.MaxMoveSpeed
      if self.distance_travelled_on_link - distance_moved_this_timestep > self.location.distance:

        # update agent logs
        if SimulationSettings.AgentLogLevel > 0:
          self.places_travelled += 1
          self.distance_travelled += self.location.distance

        # if the person has moved less than the minMoveSpeed, it should go through another evolve() step.
        evolveMore = False
        if self.location.distance + distance_moved_this_timestep < SimulationSettings.MinMoveSpeed:
          distance_moved_this_timestep += self.location.distance
          evolveMore = True

        # update location (which is on a link) to link endpoint
        self.location.numAgents -= 1
        self.location = self.location.endpoint
        self.location.numAgents += 1

        self.travelling = False
        self.distance_travelled_on_link = 0

        if SimulationSettings.CampLogLevel > 0: 
          if self.location.Camp == True:
            self.location.incoming_journey_lengths += [self.timesteps_since_departure]

        # Perform another evolve step. And if it results in travel, then the current 
        # travelled distance needs to be taken into account.
        if evolveMore == True:
          self.evolve()
          self.finish_travel(distance_moved_this_timestep)

  def getLinkWeight(self, link, awareness_level):
    """
    Calculate the weight of an adjacent link. Weight = probability that it will be chosen.
    """  

    # If turning back is NOT allowed, remove weight from the last location.
    #if not SimulationSettings.TurnBackAllowed:
    #  if link.endpoint == self.last_location:
    #    return 0.0 #float(0.1 / float(SimulationSettings.Softening + link.distance))

    return float(link.endpoint.scores[awareness_level] / float(SimulationSettings.Softening + link.distance))

  def selectRoute(self):
    linklen = len(self.location.links)
    weights = np.zeros(linklen)

    if not SimulationSettings.UseDynamicAwareness:
      for i in range(0,linklen):
        # forced redirection: if this is true for a link, return its value immediately.
        if self.location.links[i].endpoint.isFull(self.location.links[i].numAgents):
          weights[i] = 0.0
        elif self.location.links[i].forced_redirection == True:
          return i
        else:
          weights[i] = self.getLinkWeight(self.location.links[i], SimulationSettings.AwarenessLevel)
          
    else:
      for i in range(0,linklen):
        # forced redirection: if this is true for a link, return its value immediately.
        if self.location.links[i].endpoint.isFull(self.location.links[i].numAgents):
          weights[i] = 0.0
        elif self.location.links[i].forced_redirection == True:
          return i
        else:
          if self.timesteps_since_departure < 1:
            weights[i] = self.getLinkWeight(self.location.links[i], 0)
          elif self.timesteps_since_departure < 2:
            weights[i] = self.getLinkWeight(self.location.links[i], 1)
          elif self.timesteps_since_departure < 4:
            weights[i] = self.getLinkWeight(self.location.links[i], 2)
          else:
            weights[i] = self.getLinkWeight(self.location.links[i], 3)

    if len(weights) == 0:
      return -1
    else:
      if np.sum(weights) > 0.0:
        weights /= np.sum(weights)
      else: # if all have zero weight, then we do equal weighting.
        weights += 1.0/float(len(weights))

      #if len(weights) != len(list(range(0,len(self.location.links)))):
      #  print(weights, list(range(0,len(self.location.links))))

      return np.random.choice(list(range(0,len(self.location.links))), p=weights)

class Location:
  def __init__(self, name, x=0.0, y=0.0, movechance=0.001, capacity=-1, pop=0, foreign=False):
    self.name = name
    self.x = x
    self.y = y
    self.movechance = movechance
    self.links = [] # paths connecting to other towns
    self.numAgents = 0 # refugee population
    self.capacity = capacity # refugee capacity
    self.pop = pop # non-refugee population
    self.foreign = foreign
    self.Conflict = False
    self.Camp = False

    # Automatically tags a location as a Camp if refugees are less than 1% likely to move out on a given day.
    if movechance < 0.01:
      self.Camp = True

    self.LocationScore = 1.0 # Value of Location. Should be between 0.5 and SimulationSettings.CampWeight.
    self.NeighbourhoodScore = 1.0 # Value of Neighbourhood. Should be between 0.5 and SimulationSettings.CampWeight.
    self.RegionScore = 1.0 # Value of surrounding region. Should be between 0.5 and SimulationSettings.CampWeight.
    self.scores = np.array([1.0,1.0,1.0,1.0])
 
    if SimulationSettings.CampLogLevel > 0:
      self.incoming_journey_lengths = [] # reinitializes every time step. Contains individual journey lengths from incoming agents.

  def isFull(self, numOnLink):
    """ Checks whether a given location has reached full capacity. In this case it will no longer admit persons."""
    if self.capacity < 0:
      return False
    elif self.numAgents >= self.capacity*SimulationSettings.CapacityBuffer:
      return True
    return False


  def updateLocationScore(self):
    """ Attractiveness of the local point, based on local point information only. """

    if self.foreign:
      self.LocationScore = SimulationSettings.CampWeight
    elif self.Conflict:
      self.LocationScore = SimulationSettings.ConflictWeight
    else:
      self.LocationScore = 1.0
  
  def updateNeighbourhoodScore(self):

    """ Attractiveness of the local point, based on information from local and adjacent points, weighted by link length. """
    # No links connected or a Camp? Use LocationScore.
    if len(self.links) == 0 or self.Camp:
      self.NeighbourhoodScore = self.LocationScore
      return


    self.NeighbourhoodScore = 0.0
    total_link_weight = 0.0

    for i in self.links:
      self.NeighbourhoodScore += i.endpoint.LocationScore / float(i.distance)      
      total_link_weight += 1.0 / float(i.distance)

    self.NeighbourhoodScore /= total_link_weight

  def updateRegionScore(self):
    """ Attractiveness of the local point, based on neighbourhood information from local and adjacent points, 
        weighted by link length. """
    # No links connected or a Camp? Use LocationScore.
    if len(self.links) == 0 or self.Camp:
      self.RegionScore = self.LocationScore
      return

    self.RegionScore = 0.0
    total_link_weight = 0.0

    for i in self.links:
      self.RegionScore += i.endpoint.NeighbourhoodScore / float(i.distance)      
      total_link_weight += 1.0 / float(i.distance)

    self.RegionScore /= total_link_weight
    self.scores = np.array([1.0, self.LocationScore, self.NeighbourhoodScore, self.RegionScore])

class Link:
  def __init__(self, endpoint, distance, forced_redirection=False):

    # distance in km.
    self.distance = float(distance)

    # links for now always connect two endpoints
    self.endpoint = endpoint

    # number of agents that are in transit.
    self.numAgents = 0

    # if True, then all Persons will go down this link.
    self.forced_redirection = forced_redirection


class Ecosystem:
  def __init__(self):
    self.locations = []
    self.locationNames = []
    self.agents = []
    self.time = 0

    # Bring conflict zone management into FLEE.
    self.conflict_zones = []
    self.conflict_zone_names = []
    self.conflict_weights = np.array([])
    self.conflict_pop = 0

    if SimulationSettings.CampLogLevel > 0:
      self.num_arrivals = [] # one element per time step.
      self.travel_durations = [] # one element per time step.

  def _aggregate_arrivals(self):
    """
    Add up arrival statistics, to find out travel durations and total number of camp arrivals.
    """
    if SimulationSettings.CampLogLevel > 0:
      arrival_total = 0
      tmp_num_arrivals = 0 

      for l in self.locations:
        if l.Camp == True:
          arrival_total += np.sum(l.incoming_journey_lengths)
          tmp_num_arrivals += len(l.incoming_journey_lengths)
          l.incoming_journey_lengths = []

      self.num_arrivals += [tmp_num_arrivals]

      if tmp_num_arrivals>0:
        self.travel_durations += [float(arrival_total) / float(tmp_num_arrivals)]
      else:
        self.travel_durations += [0.0]

      #print("New arrivals: ", self.travel_durations[-1], arrival_total, tmp_num_arrivals)    

  def remove_link(self, startpoint, endpoint):
    """Remove link when there is border closure between countries"""
    new_links = []

    x = -1
    # Convert name "startpoint" to index "x".
    for i in range(0, len(self.locations)):
      if(self.locations[i].name == startpoint):
        x = i

    if x<0:
      print("#Warning: location not found in remove_link")

    for i in range(0, len(self.locations[x].links)):
      if self.locations[x].links[i].endpoint.name is not endpoint:
        new_links += [self.locations[x].links[i]]

    self.location[x].links = new_links


  def add_conflict_zone(self, name, change_movechance=True):
    """
    Adds a conflict zone. Default weight is equal to population of the location.
    """
    for i in range(0, len(self.locationNames)):
      if self.locationNames[i] == name:
        if name not in self.conflict_zone_names:
          if change_movechance:
            self.locations[i].movechance = 1.0
            self.locations[i].Conflict = True
          self.conflict_zone_names += [name]
          self.conflict_zones += [self.locations[i]]
          self.conflict_weights = np.append(self.conflict_weights, [self.locations[i].pop])
          self.conflict_pop = sum(self.conflict_weights)
          if SimulationSettings.InitLogLevel > 0:
            print("Added conflict zone:", name, ", pop. ", self.locations[i].pop)
            print("New total pop. in conflict zones: ", self.conflict_pop) 
          return

    print("Diagnostic: self.locationNames: ", self.locationNames)
    print("ERROR in flee.add_conflict_zone: location with name ", name, " appears not to exist in the FLEE ecosystem (see diagnostic above).")


  def remove_conflict_zone(self, name):
    """
    Shorthand function to remove a conflict zone from the list.
    (not used yet)
    """
    new_conflict_zones = []
    new_conflict_zone_names = []
    new_weights = np.array([])

    for i in range(0, len(self.conflict_zones)):
      if conflict_zones[i].name is not name:
        new_conflict_zones += [self.conflict_zones[i]]
        new_conflict_zone_names += [self.conflict_zone_names[i]]
        new_weights = np.append(new_weights, [self.conflict_weights[i]])

    self.conflict_zones = new_conflict_zones
    self.conflict_weights =  new_weights
    self.conflict_pop = sum(self.conflict_weights)


  def pick_conflict_location(self):
    """
    Returns a weighted random element from the list of conflict locations.
    This function returns a number, which is an index in the array of conflict locations.
    """
    return np.random.choice(self.conflict_zones, p=self.conflict_weights/self.conflict_pop)


  def refresh_conflict_weights(self):
    """
    This function needs to be called when SimulationSettings.TakeRefugeesFromPopulation is set to True.
    It will update the weights to reflect the new population numbers.
    """
    for i in range(0,len(self.conflict_zones)):
      self.conflict_weights[i] = self.conflict_zones[i].pop
    self.conflict_pop = sum(self.conflict_weights)


  def evolve(self):
    # update level 1, 2 and 3 location scores
    for l in self.locations:
      l.updateLocationScore() 

    for l in self.locations:
      l.updateNeighbourhoodScore() 

    for l in self.locations:
      l.updateRegionScore() 

    #update agent locations
    for a in self.agents:
      a.evolve()

    for a in self.agents:
      a.finish_travel()

    #update link properties
    if SimulationSettings.CampLogLevel > 0:
      self._aggregate_arrivals()
    self.time += 1

  def addLocation(self, name, x="0.0", y="0.0", movechance=0.1, capacity=-1, pop=0, foreign=False):
    l = Location(name, x, y, movechance, capacity, pop, foreign)
    if SimulationSettings.InitLogLevel > 0:
      print("Location:", name, x, y, movechance, capacity, ", pop. ", pop, foreign)
    self.locations.append(l)
    self.locationNames.append(l.name)
    return l


  def addAgent(self, location):
    if SimulationSettings.TakeRefugeesFromPopulation:
      if location.pop > 0:
        location.pop -= 1
    self.agents.append(Person(location))

  def numAgents(self):
    return len(self.agents)


  def linkUp(self, endpoint1, endpoint2, distance="1.0", forced_redirection=False):
    """ Creates a link between two endpoint locations
    """
    endpoint1_index = -1
    endpoint2_index = -1
    for i in range(0, len(self.locationNames)):
      if(self.locationNames[i] == endpoint1):
        endpoint1_index = i
      if(self.locationNames[i] == endpoint2):
        endpoint2_index = i

    if endpoint1_index < 0:
      print("Diagnostic: Ecosystem.locationNames: ", self.locationNames)
      print("Error: link created to non-existent source: ", endpoint1, " with dest ", endpoint2)
      sys.exit()
    if endpoint2_index < 0:
      print("Diagnostic: Ecosystem.locationNames: ", self.locationNames)
      print("Error: link created to non-existent destination: ", endpoint2, " with source ", endpoint1)
      sys.exit()

    self.locations[endpoint1_index].links.append( Link(self.locations[endpoint2_index], distance, forced_redirection) )
    self.locations[endpoint2_index].links.append( Link(self.locations[endpoint1_index], distance) )

  def printInfo(self):

    print("Time: ", self.time, ", # of agents: ", len(self.agents))
    for l in self.locations:
      print(l.name, l.numAgents)


if __name__ == "__main__":
  print("Flee, prototype version.")

  end_time = 50
  e = Ecosystem()

  l1 = e.addLocation("Source")
  l2 = e.addLocation("Sink1")
  l3 = e.addLocation("Sink2")

  e.linkUp("Source","Sink1","10.0")
  e.linkUp("Source","Sink2","5.0")

  for i in range(0,100):
    e.addAgent(location=l1)

  for t in range(0,end_time):
    e.evolve()
    e.printInfo()
    
