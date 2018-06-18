"""Software for planning of nightshifts of doctors at my Hospital.
   Author: Alexandr Škaryd MD
   skaryd81 at gmail dot com
   Ver.: SKYNET v 0.5
   Licence: GNU General Public License v3.0
   Status: allways finds a solution. Can miss a best solution.

   The software creates an optimal pattern of nightshifts for doctors based on 
   their preference (ie. they can say which days they would love to work and 
   on which days they dont want or can not work).

   The method is a genetic algorithm.
   The input is a time span in format of 2018-01-01 to 2018-01-31 for example.
   The input are text files:

   docold.txt - a list of all names of all senior doctors
   docyoung.txt - a list of all names of all junior doctors
   svatky.txt - a list of days which are like weekend days due to holiday
   *.txt - each name from docold or docyoung has an appropriate .txt file

   Config files for each worker in this format.
   1 - number of workdays or X, where X will distribute evenly among X
   2 - number of weekends or X
   3 - employment (0.5 could mean to expect half the workdays and weekends)
   4 - minimal interval between nightshifts
   5 - number of days with index 1 - deprecated 
   6 - number of days with index 1.125 - deprecated
   7 - number of days with index 1.25 - not used atm
   8 - number of days with index 1.3 - not used atm
   9 - number of days with index 1.37 - not used atm
   12 - list of days on which the workers WANTS to work
   13 - keyword NEMUZE marking the end of WANTED days
   14 - list of days on which the worker DOESNT want to work
   """

#Imports
from datetime import timedelta, datetime
import random, statistics, copy

#Constants
WorkersFilename = "docold.txt"
OverrideFilename = "overold.txt"
SourceAbeceda = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
Population_count = 5 #5 not used at the moment
PopulationSize = 350 #200 usually
MutationRate = 20 #percentage of mutations, could be variable in time / cycle
CrossoverRate = 50 #percentage of crossover rate
Cycles = 200 #200
ElitePercentage = 10 #percentage of population seeded from Elite specimens.
#Penalties in low numbers tend to find better solutions.
Penalty_interval = 2 #300 for final evaluation
Penalty_weekend = 1 #150 
Penalty_fridays = 1 #50
Penalty_count = 2 #1000
Penalty_critical = 3
"""
Fitness calculation.. the higher the better. We subtract actual penalties from
 theoretical maximum to do this.
Therefore we get in this scenario a 9 maximum and with 2 actual we get 7.
"""
Theoretical_fitness = Penalty_interval + Penalty_weekend + Penalty_fridays + Penalty_count + Penalty_critical+1

#Classes
class Worker(object): 
    """ A class to hold all info needed for a single worker

    letter is an assigned letter unique for each worker from SourceAbeceda
    employment is a float in range 0,1 that limits amount of labour
    min_interval is a minimum interval between two nightshifts 
    i1 through i37 is not used atm, planned to use to count day types
    limit_workday is either a number of expected nightshifts or an "X" for avg
    limit_weekend is either a number of expected nightshifts or an "X" for avg
    desired_duty array of DayOfLife objects, dates on which worker wants work
    undesired_duty array of DayOfLife objects, dont want to work here

    """

    def __init__(self, letter, employment, min_interval, i1, i125, i25, i3, i37, limit_workday, limit_weekend, desired_duty = [], undesired_duty = []):
        self.letter = letter
        self.employment = employment
        self.min_interval = min_interval
        self.i1 = i1
        self.i125 = i125
        self.i25 = i25
        self.i3 = i3
        self.i37 = i37
        self.limit_workday = limit_workday
        self.limit_weekend = limit_weekend
        self.desired_duty = desired_duty
        self.undesired_duty = undesired_duty

class DayOfLife(object): 
    """ A class to store all data about a single day specific in time span

    index Mon Tue Wed 1.125, Thu 1, Fri 1.25, Sat 1.37, Sun 1.3
    possible_duty is array with Workers who can work on the specific day
    worker is a definite worker to work on the day. Possibly UNNECESSARY

    """

    def __init__(self, index, worker, possible_duty = []):
        self.index = index
        self.possible_duty = possible_duty
        self.worker = worker

class Population(object): 
    """ A class to store all data about a single population 

    maxfitness is maximum fitness encountered in this population
    minfitness is minimum fitness 
    sequences is array of sequences / entities in this populations
    a sequence is a class object
    
    """

    def __init__(self, maxfitness, minfitness, sequences = []):
        self.sequences = sequences
        self.maxfitness = maxfitness
        self.minfitness = minfitness

class Sequence(object): 
    """ A class to hold data about a sequence

    workers is a string made of worker letters, where each pos is a day
    fitness is the measured fitness of the current sequence

    """

    def __init__(self, fitness, workers):
        self.workers = workers
        self.fitness = fitness

#Functions
def load_worker_sources(filename):
    """ Reads data from config files of all workers

    Loads up all workers from files based on a superfile containing all names
    it should receive information and save it into a data type that is 
    returned.

    """
    with open(filename) as f:
        content = f.readlines()
        content = [x.strip() for x in content]
        
    workers = {}

    #for each name in the superfile we open a name.txt and get the data.
    for x in content:
        #create new worker variable
        loading_worker = Worker(0,0,0,0,0,0,0,0,0,[],[])
        #generate file name
        filename = x + ".txt"
        #one by one open all files and fill the workers into a dictionary
        with open(filename) as f:
            loading_worker.limit_workday = f.readline().strip()
            loading_worker.limit_weekend = f.readline().strip()
            loading_worker.employment = f.readline().strip()
            loading_worker.min_interval = f.readline().strip()
            loading_worker.i1 = f.readline().strip()
            loading_worker.i125 = f.readline().strip()
            loading_worker.i25 = f.readline().strip()
            loading_worker.i3 = f.readline().strip()
            loading_worker.i37 = f.readline().strip()
            source = f.readlines()
            source = [x.strip() for x in source] #convert lines into entries
            desires =  []
            desiresnot = []
            i = 0
            """
            This cycle stores WANTED dates untill it encounters a keyword on 
            which it breaks and stores any further entries as UNWANTED
            NEMUZE means IS UNABLE TO in Czech my native language
            """
            while i < len(source):
                if source[i] != "NEMUZE": 
                    desires.append(source[i])
                if source[i] == "NEMUZE":
                    i+=1
                    break
                i+=1
            while i < len(source):
                desiresnot.append(source[i])
                i+=1
            loading_worker.desired_duty = desires
            loading_worker.undesired_duty = desiresnot
            workers[x] = loading_worker
    
    #we assign each worker unique letter from the alphabet
    currentAbeceda = SourceAbeceda[:len(workers)]
    i = 0
    for key in workers:
        workers[key].letter = currentAbeceda[i]
        i += 1
   
    return [workers, currentAbeceda]

def calendar_interval_get(): 
    """ Set first and last day of the time span we write nightshifts for."""

    start_rok = int(2018)
    start_mesic= int(7)
    start_den = int(1)
    end_year = int(2018)
    end_month = int(7)
    end_day = int(31)
    first_day = datetime(start_rok, start_mesic, start_den)
    last_day = datetime(end_year, end_month, end_day)
    return (first_day, last_day)

def calendar_genesis(first_day,last_day):
    """ Create a datatype representing a calendar of days in time span.

    We create a DayOfLife object for each date in the time span. 
    We assign index based on day type to each day.
    We override those indexes on days with holidays.
    
    """

    dateList = {} 
    day_count = (last_day - first_day).days +1

    #this speeds up assigning of indexes to days in the for cycle below
    indexes = {"1" : float(1.125), "2" : float(1.125),"3" : float(1.125),"4" : float(1.01),"5" : float(1.25),"6" : float(1.37),"7" : float(1.3)}

    """
    The cycle parses each day in the calendar and assigns index, 
    creates a new day, assigns date and adds the new day into the list.
    """

    for single_date in (first_day + timedelta(n) for n in range(day_count)):
        index = indexes.get(str(single_date.isoweekday()))
        new_day = DayOfLife(index,[])
        dateList[single_date.strftime('%Y-%m-%d')] = new_day
        
    """
    Load up holidays from a list of holidays in a file svatky.txt
    """

    content = {}
    with open("svatky.txt") as f:
        i = 0
        for line in f:
            #we split each line into date and index
            splitLine = line.split()
            content[(splitLine[0])] = " ".join(splitLine[1:])
            i += 1

    #We update the calendar with the overriden holiday days
    for key in dateList:
        if key in content:
            dateList[key].index = float(content[key]) 

    return dateList

def calendar_availability(kalendar_source,workers_sources):
    """ Assign each day in calendar an array of workers who can WORK. """
    
    """
    Probably unnecesarry, could use kalendar_source? Want to make sure i
    return updated data
    """
    calendar = kalendar_source 
    
    #i feel unable to combine the two cycles into one, feels possible though
    for day in calendar:
        calendar[day].possible_duty = [] 
        for key in workers_sources:
            if day not in workers_sources[key].undesired_duty:
                calendar[day].possible_duty.append(workers_sources[key].letter)

    for day in calendar:
        first = True
        den = calendar.get(day)
        for key in workers_sources:
            if day in workers_sources[key].desired_duty:
                if first == True:
                    den.possible_duty = []
                    den.possible_duty.append(workers_sources[key].letter)
                    first = False
                else:
                    den.possible_duty.append(workers_sources[key].letter)
        calendar[day] = den

    return calendar

def timespan_ideal_values(kalendar_source,workers_sources): 
    """ Counts ideal counts of nightshifts for workers with X reguirements."""

    minus_weekend = 0
    weekend_workers = 0
    minus_workday = 0
    workday_workers = 0
    total_workday = 0
    total_weekend = 0
    avg_index = 0

    for key in workers_sources:
        if workers_sources[key].limit_workday != "X":
            workers_sources[key].limit_workday = int(workers_sources[key].limit_workday)
            minus_workday += float(workers_sources[key].limit_workday)
        else:
            workday_workers += 1 #count the people who dont have fixed counts
        if workers_sources[key].limit_weekend != "X":
            workers_sources[key].limit_weekend = int(workers_sources[key].limit_weekend)
            minus_weekend += float(workers_sources[key].limit_weekend)
        else:
            weekend_workers += 1 #count the people who dont have fixed counts

    for day in kalendar_source:
        if kalendar_source[day].index > 1.29:
            total_weekend += 1
        else:
            total_workday += 1

    ideal_workday = 0
    ideal_workday = total_workday - minus_workday
    ideal_workday = ideal_workday / workday_workers
    ideal_weekend = 0
    ideal_weekend = total_weekend - minus_weekend
    ideal_weekend = ideal_weekend / weekend_workers

    return (ideal_workday, ideal_weekend)

def generate_random_Sequence(abeceda, kalendar, firstday): 
    """ Generate random sequence from possible workers each day.

    We generate a string with each position being a day and each letter a 
    worker. We use letters to be able to read results directly.

    """
    
    random_Sequence = Sequence(0,"")
    
    i = 0
    while i < len(kalendar):
        current_date = firstday + timedelta(days = i)
        current_date = current_date.strftime('%Y-%m-%d')

        random_Sequence.workers += (random.choice(kalendar[current_date].possible_duty))
        i += 1

    return random_Sequence

def generate_first_population(size, abeceda, kalendar, firstday): 
    """ We create the first population.

    We fill as many new random sequences as is the population size.

    """

    first_Population = Population(0,[])
    i = 0
    while i < (size):
        first_Population.sequences.append(generate_random_Sequence(abeceda, kalendar, firstday))
        i = i + 1

    #make sure the max is allways bigger then default and min allways smaller.
    first_Population.maxfitness = 0
    first_Population.minfitness = 40000

    return first_Population

def update_workers_with_ideal_values(workers,ideal_workday,ideal_weekend): 
    """ Update all workers with ideal values if thez have X as reguirement."""

    for key in workers:
        if workers[key].limit_workday == "X":
           workers[key].limit_workday = ideal_workday * float(workers[key].employment)
        if workers[key].limit_weekend == "X":
           workers[key].limit_weekend = ideal_weekend * float(workers[key].employment)
    
    return workers

def count_population_fitness(Population, currentAbeceda, workers, kalendar, firstday, ideal_fridays):
    """ We need to find the best specimen from the population.

    We count fitness of all sequences from the population and get the maximum.
    We should probably store the Best_speciment here and save it in the 
    population in the future and not have it stored outside.

    """

    for key in Population.sequences:
        key.fitness = entity_fitness(workers,key,kalendar,firstday,ideal_fridays)
        if key.fitness > Population.maxfitness:
            Population.maxfitness = key.fitness
        if key.fitness < Population.minfitness:
            Population.minfitness = key.fitness

    return [Population.maxfitness,Population.minfitness]

def get_ideal_friday(workers, kalendar, firstday): 
    """ We count all fridays and divide them among total workers."""

    fridays = 0
    for key in kalendar:
        if kalendar[key].index == 1.25:
            fridays += 1

    result = fridays / len(workers)

    return result

def entity_fitness(workers,Sequence,kalendar,firstday,ideal_fridays): 
    """ The mainstay of the Genetic Algorithm, measure fitness of sequence.

    We detect all nightshifts in the sequence for each worker. We then measure
    the intervals between all nighshifts. Interval between fridays and weekend
    days nightshifts and count the total numbers and assign penalties where
    appropriate.

    We then subtract the total penalties from the maximum penalties to get
    a "The higher the better" result.

    """
    total_fitness = 0

    for key in workers:
        currentWorker = Worker(0,0,0,0,0,0,0,0,0,0,[],[])
        currentWorker = workers[key]
        limit_workday = currentWorker.limit_workday
        limit_weekend = currentWorker.limit_weekend
        duties = []
        duties_p = []
        duties_friday = []
        duties_weekend = []
        weekend = -1
        workdays = -1
        fridays = -1
        penalty_count = 0
        penalty_interval = 0
        penalty_critical = 0
        penalty_weekend = 0
        penalty_fridays = 0
        penalty = 0

        # Here we sort nighshifts assigned into Mo-Th + Fr + Sat-Sun
        
        yy = 0
        while yy < len (Sequence.workers):
            current_date = firstday + timedelta(days = yy)
            current_date = current_date.strftime('%Y-%m-%d')
            if Sequence.workers[yy] == currentWorker.letter:
                if kalendar[current_date].index == 1.125 : #Mo Tu We
                    duties_p.append(yy)
                if kalendar[current_date].index == 1.01 : #Th
                    duties_p.append(yy)
                if kalendar[current_date].index == 1.25 : #Friday
                    duties_friday.append(yy)
                if kalendar[current_date].index == 1.3 : #Sunday
                    duties_weekend.append(yy)
                if kalendar[current_date].index == 1.37 : #Saturday
                    duties_weekend.append(yy)
            yy +=1

        """
        # nighshift count should be equal or +1 to the asking value if X
        If hardcoded and not X, it should equal the integer number.
        This functionality is not yet built in.

        We probably want to split weekend and workday penalty into two
        penalties. Since at the moment it is NONCUMULATIVE. 

        """

        if int(limit_weekend) <= len(duties_weekend) <= int(limit_weekend)+1:
            pass
        else:
            penalty_count = Penalty_count 
            
        #add friday + weekend shifts into one array and sort by date
        duties_pv = duties_friday + duties_weekend 
        duties_pv = list(dict.fromkeys(duties_pv))
        duties_pv.sort(key=int)

        #add basic + friday shifts into one array and sort by date
        duties_p = duties_p + duties_friday
        duties_p = list(dict.fromkeys(duties_p))
        duties_p.sort(key=int)

        #add all duties into one array
        duties = duties_p + duties_pv 
        duties = list(dict.fromkeys(duties))
        duties.sort(key=int)

        """
        # nighshift count should be equal or +1 to the asking value if X
        If hardcoded and not X, it should equal the integer number.
        This functionality is not yet built in.
        """
        if int(limit_workday) <= len(duties_p) <= int(limit_workday)+1:
            pass
        else:
            penalty_count = Penalty_count 

        # we penalize wrong total number toom should have own penalty probably
        if int(limit_workday+limit_weekend) <= len(duties) <= int(limit_workday+limit_weekend)+1: 
            pass
        else:
            penalty_count += Penalty_count

        # we penalize if someone has more fridays then average.
        fridays = len(duties_friday)
        if int(ideal_fridays) <= fridays <=  int(ideal_fridays)+1:
            pass
        else:
            penalty_fridays = Penalty_fridays 

        """
        We go through Fri Sat Sun nighshifts by index to see, whether there
        are more then 1 within 10 days, which is not desired. I fail to see
        how i could do that with a FOR loop.
        
        """

        xx = 0
        while xx < len(duties_pv): 
            if xx!=0:
                if duties_pv[xx]-duties_pv[xx-1]<10:
                    penalty_weekend = Penalty_weekend 
            xx += 1

        """
        We go through ALL nighshifts by index to find out the intervals between
        nighshifts. We penalize all below min_interval by worker.
        We penalize ALL Intervals of 1 since ONE CAN NOT have TWO nighshifts
        after each with a CRITICAL penalty which should basically remove such
        sequence from existance.
        I fail to see how i could do that with a FOR loop.
        
        """

        xx = 0
        while xx < len(duties):
            if xx!=0:
                if duties[xx]-duties[xx-1]<(int(currentWorker.min_interval)+1):  
                    if duties[xx]-duties[xx-1] == 1:
                        penalty_critical = Penalty_critical 
                    else:
                        penalty_interval = Penalty_interval
            xx += 1

        #combine all received penalties
        penalty = penalty_count + penalty_fridays + penalty_weekend + penalty_interval + penalty_critical
        fitness = 0
        """
        Subtract them from theoretical maximum to get a "the higher the better"
        result.

        """

        fitness = Theoretical_fitness - penalty
        total_fitness += fitness

    return total_fitness

def fin_entity_fitness(workers,Sequence,kalendar,firstday,ideal_fridays): 
    """ Count entity fitness, but use different penalties with scaling

    THIS IS basically a CLONE of entity_fitness function above, a product of 
    lazyness. This entire function could be removed and some activators 
    implemented into entity_fitness to enable evaluating of the sequence
    by different penalty values if reguired..

    """

    total_fitness = 0
    Penalty_interval = 300 #300
    Penalty_weekend = 150 #150
    Penalty_fridays = 50 #50
    Penalty_count = 1000 #1000
    Penalty_critical = 1500
    Theoretical_fitness = Penalty_interval + Penalty_critical + Penalty_weekend + Penalty_fridays + Penalty_count 

    for key in workers:
        currentWorker = Worker(0,0,0,0,0,0,0,0,0,0,[],[])
        currentWorker = workers[key]
        limit_workday = currentWorker.limit_workday
        limit_weekend = currentWorker.limit_weekend
        duties = []
        duties_p = []
        duties_friday = []
        duties_weekend = []
        weekend = -1
        workdays = -1
        fridays = -1
        penalty_count = 0
        penalty_interval = 0
        penalty_weekend = 0
        penalty_fridays = 0
        penalty = 0

        yy = 0
        while yy < len (Sequence.workers):
            current_date = firstday + timedelta(days = yy)
            current_date = current_date.strftime('%Y-%m-%d')
            if Sequence.workers[yy] == currentWorker.letter:
                if kalendar[current_date].index == 1.125 : #Po Ut St
                    duties_p.append(yy)
                if kalendar[current_date].index == 1.01 : #Ctvrtek
                    duties_p.append(yy)
                if kalendar[current_date].index == 1.25 : #friday
                    duties_friday.append(yy)
                if kalendar[current_date].index == 1.3 : #nedele
                    duties_weekend.append(yy)
                if kalendar[current_date].index == 1.37 : #sobota
                    duties_weekend.append(yy)
            yy +=1

        if int(limit_weekend) <= len(duties_weekend) <= int(limit_weekend)+1:
            pass
        else:
            print ("Penalty for count of nightshifts",key)
            penalty_count = Penalty_count 
            
        duties_pv = duties_friday + duties_weekend 
        duties_pv = list(dict.fromkeys(duties_pv))
        duties_pv.sort(key=int)

        duties_p = duties_p + duties_friday
        duties_p = list(dict.fromkeys(duties_p))
        duties_p.sort(key=int)

        duties = duties_p + duties_pv 
        duties = list(dict.fromkeys(duties))
        duties.sort(key=int)

        if int(limit_workday) <= len(duties_p) <= int(limit_workday)+1:
            pass
        else:
            print ("Penalty for count of workday",key)
            penalty_count = Penalty_count

        if int(limit_workday+limit_weekend) <= len(duties) <= int(limit_workday+limit_weekend)+1:
            pass
        else:
            print ("Penalty for count of weekend",key)
            penalty_count += Penalty_count 

        fridays = len(duties_friday)
        if int(ideal_fridays) <= fridays <=  int(ideal_fridays)+1:
            pass
        else:
            print ("Penalty for count of fridays",key)
            penalty_fridays = Penalty_fridays

        xx = 0
        while xx < len(duties_pv):
            if xx!=0:
                if duties_pv[xx]-duties_pv[xx-1]<10:
                    print ("Penalty for weekend interval",key)
                    penalty_weekend = Penalty_weekend 
            xx += 1
        
        xx = 0
        while xx < len(duties):
            if xx!=0:
                if duties[xx]-duties[xx-1]<(int(currentWorker.min_interval)+1): 
                    if duties[xx]-duties[xx-1]== 1:
                        penalty_critical = Penalty_critical 
                        print ("Critical penalty",key)
                    else:
                        penalty_interval = Penalty_interval 
            xx += 1

        penalty = penalty_count + penalty_fridays + penalty_weekend + penalty_interval
        fitness = 0
        fitness = Theoretical_fitness - penalty 
        total_fitness += fitness

    return total_fitness

def create_selection_pool(currentAbeceda, PopulationS, kalendar, first_day, maxfitness, minfitness): 
    """ Create a pool of sequences with amounts based on their quality

    We multiply each sequence occurence in the pool based on its fitness.
    We also remove sub-average sequences from "the game" before that.

    """

    hat = Population(0,0,[])
    ratio = (maxfitness +1 - minfitness)/100
    total_fitness = 0
    highest_fitness = 0
    entity_count = len(PopulationS.sequences)
    
    #we remove below average specimens from the population first
    for key in PopulationS.sequences:
        total_fitness += key.fitness
        if key.fitness > highest_fitness:
            highest_fitness = key.fitness
    average_fitness = total_fitness / entity_count
    for key in PopulationS.sequences:
        if key.fitness < average_fitness:
            PopulationS.sequences.remove(key)

    """we breed the remaining specimens to fill the hat or breeding pool."""

    x = 0
    specimen = Sequence(0,"")
    for key in PopulationS.sequences:
        if key.fitness == maxfitness:
            specimen = key
    
    for key in PopulationS.sequences:
        i = 0
        while i < ((key.fitness +1 - minfitness)/ratio):
            hat.sequences.append(key)
            i += 1

    #we return the pool / hat and the best specimen in it
    return hat, specimen

def mutate(currentAbeceda, mutation_chance, entity, kalendar, firstday): 
    """ Perform mutation upon a sequence / entity using mutation chance."""

    i = 0

    new_entity = ""
    while i < len(entity):
        current_date = firstday + timedelta(days = i)
        current_date = current_date.strftime('%Y-%m-%d')
        if random.randint(0, 100) < mutation_chance:
            test = random.choice(kalendar[current_date].possible_duty)
            new_entity += test
        else:
            new_entity += entity[i]
        i += 1

    return new_entity

def generate_population(hat, population_size, mutation, kalendar, first_day, elite_specimen): 
    """ We pick random sequences from the hat and breed them.

    We handpick parents from the pool / hat and crossover them to create 
    hybrid children which we send over. Problem here is that the crossover
    function is basically a random switch between the two parents.
    For future there need to be specific crossover points probably Mondays.
    
    """

    new_population = Population(0,0,[])

    #First we introduce a certain number of elite speciments
    x = 0
    while x < population_size/ElitePercentage: 
        new_population.sequences.append(elite_specimen)
        x += 1

    #then we fill the rest with specimens that we crossover
    while x < (population_size/2-population_size/ElitePercentage): 
        parentAR = Sequence(0,"")
        parentBR = Sequence(0,"")
        parentAR = random.choice(hat.sequences)
        parentBR = random.choice(hat.sequences)

        #crossover
        parentA = parentAR.workers
        parentB = parentBR.workers

        y = 1
        childA = parentA[:1]
        childB = parentB[:1]

        while y < len(parentA):
            """
            #we basically put along two specimens, and switch letters if the 
            chance is right = crossover rate constant, for each location in
            the string. More correct would be to crossover entire sections
            from monday to sunday for example. 

            """

            rand_number = random.randint (0,1) 
            if rand_number == 0:
                childA = childA[:y] + parentA[y:]
                childB = childB[:y] + parentB[y:]
            if rand_number == 1:
                childA = childA[:y] + parentB[y:]
                childB = childB[:y] + parentA[y:]
            y += 1

        childAR = Sequence(0,"")
        childBR = Sequence(0,"")

        childAR.workers = childA
        childBR.workers = childB

        childAR.workers = mutate(abeceda,mutation,childAR.workers,kalendar, first_day)
        childBR.workers = mutate(abeceda,mutation,childBR.workers,kalendar, first_day)

        #we inject two children per two parents into the population
        new_population.sequences.append(childAR) 
        new_population.sequences.append(childBR)
        x += 1

    return new_population

def save_results(kalendar): 
    """ save the final results into a text file."""

    with open("results.txt", "w") as f:
        for day in kalendar:
            #content = day  + " " + kalendar[day].worker + "\n"
            f.write (kalendar[day].worker + "\n")
    return True

#CORE 
if __name__ == "__main__":
    Best_specimen_af = Sequence(0,"")
    Elite_specimen_af = Sequence(0,"")
    Best_specimen_eu = Sequence(0,"")
    Elite_specimen_eu = Sequence(0,"")
    Best_specimen_au = Sequence(0,"")
    Elite_specimen_au = Sequence(0,"")
    Best_specimen_am = Sequence(0,"")
    Elite_specimen_am = Sequence(0,"")
    Best_specimen_an = Sequence(0,"")
    Elite_specimen_an = Sequence(0,"")
    Best_specimen = Sequence(0,"")

    workers_sources, abeceda = load_worker_sources(WorkersFilename) 
    first_day, last_day = calendar_interval_get() 
    kalendar_source = calendar_genesis(first_day,last_day) 
    kalendar_source = calendar_availability(kalendar_source,workers_sources)
    ideal_fridays = get_ideal_friday(workers_sources,kalendar_source,first_day) 
    ideal_workday, ideal_weekend = timespan_ideal_values(kalendar_source,workers_sources)
    workers_sources = update_workers_with_ideal_values(workers_sources,ideal_workday,ideal_weekend) 

    """ Rework this into an array of populations for the future.
    
    This mutliple island approach has higher chance of various solutins to compete
    for supremacy.
    Also NO IDEA how to bring those lines below 79 columns for easz reading. 

    """
    first_Population_africa = generate_first_population(PopulationSize, abeceda, kalendar_source, first_day) 
    first_Population_eurasia = generate_first_population(PopulationSize, abeceda, kalendar_source, first_day) 
    first_Population_australia = generate_first_population(PopulationSize, abeceda, kalendar_source, first_day)
    first_Population_america = generate_first_population(PopulationSize, abeceda, kalendar_source, first_day) 
    first_Population_antarktis = generate_first_population(PopulationSize, abeceda, kalendar_source, first_day)

    maxfitness_af, minfitness_af = count_population_fitness(first_Population_africa,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)
    print ("Africa generated.")
    maxfitness_eu, minfitness_eu = count_population_fitness(first_Population_eurasia,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays) 
    print ("Eurasia generated.")
    maxfitness_au, minfitness_au = count_population_fitness(first_Population_australia,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays) 
    print ("Australia generated.")
    maxfitness_am, minfitness_am = count_population_fitness(first_Population_america,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays) 
    print ("America generated.")
    maxfitness_an, minfitness_an = count_population_fitness(first_Population_antarktis,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays) 
    print ("Antarktis generated.")
    hat_selekce_af, Best_specimen_af = create_selection_pool(abeceda, first_Population_africa, kalendar_source, first_day, maxfitness_af, minfitness_af)
    hat_selekce_eu, Best_specimen_eu = create_selection_pool(abeceda, first_Population_eurasia, kalendar_source, first_day, maxfitness_eu, minfitness_eu) 
    hat_selekce_au, Best_specimen_au = create_selection_pool(abeceda, first_Population_australia, kalendar_source, first_day, maxfitness_au, minfitness_au) 
    hat_selekce_am, Best_specimen_am = create_selection_pool(abeceda, first_Population_america, kalendar_source, first_day, maxfitness_am, minfitness_am) 
    hat_selekce_an, Best_specimen_an = create_selection_pool(abeceda, first_Population_antarktis, kalendar_source, first_day, maxfitness_an, minfitness_an)

    Population_af = generate_population(hat_selekce_af,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_af)
    Population_eu = generate_population(hat_selekce_eu,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_eu) 
    Population_au = generate_population(hat_selekce_au,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_au) 
    Population_am = generate_population(hat_selekce_am,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_am) 
    Population_an = generate_population(hat_selekce_an,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_an) 
    
    u = 0
    print ("Beginning phase 1.") #there should have been a phase 2 with different mutation rate one day

    while (u < Cycles) and (Best_specimen.fitness != Theoretical_fitness*len(workers_sources)): 
        print ("Done from ", u/(Cycles/100)," procent.", end = "\r")

        maxfitness_af, minfitness_af = count_population_fitness(Population_af,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)
        maxfitness_eu, minfitness_eu = count_population_fitness(Population_eu,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)
        maxfitness_au, minfitness_au = count_population_fitness(Population_au,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)
        maxfitness_am, minfitness_am = count_population_fitness(Population_am,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)
        maxfitness_an, minfitness_an = count_population_fitness(Population_an,abeceda,workers_sources,kalendar_source,first_day,ideal_fridays)

        hat_selekce_af, Elite_specimen_af = create_selection_pool(abeceda, Population_af, kalendar_source, first_day, maxfitness_af, minfitness_af)
        hat_selekce_eu, Elite_specimen_eu = create_selection_pool(abeceda, Population_eu, kalendar_source, first_day, maxfitness_eu, minfitness_eu) 
        hat_selekce_au, Elite_specimen_au = create_selection_pool(abeceda, Population_au, kalendar_source, first_day, maxfitness_au, minfitness_au)
        hat_selekce_am, Elite_specimen_am = create_selection_pool(abeceda, Population_am, kalendar_source, first_day, maxfitness_am, minfitness_am)
        hat_selekce_an, Elite_specimen_an = create_selection_pool(abeceda, Population_an, kalendar_source, first_day, maxfitness_an, minfitness_an)
    
        if Elite_specimen_af.fitness >= Best_specimen_af.fitness: 
            Best_specimen_af = Elite_specimen_af
            if Best_specimen_af.fitness > Best_specimen.fitness:
                Best_specimen = Best_specimen_af
        if Elite_specimen_eu.fitness >= Best_specimen_eu.fitness:
            Best_specimen_eu = Elite_specimen_eu
            if Best_specimen_eu.fitness > Best_specimen.fitness:
                Best_specimen = Best_specimen_eu
        if Elite_specimen_au.fitness >= Best_specimen_au.fitness:
            Best_specimen_au = Elite_specimen_au
            if Best_specimen_au.fitness > Best_specimen.fitness:
                Best_specimen = Best_specimen_au
        if Elite_specimen_am.fitness >= Best_specimen_am.fitness:
            Best_specimen_am = Elite_specimen_am
            if Best_specimen_am.fitness > Best_specimen.fitness:
                Best_specimen = Best_specimen_am
        if Elite_specimen_an.fitness >= Best_specimen_an.fitness:
            Best_specimen_an = Elite_specimen_an
            if Best_specimen_an.fitness > Best_specimen.fitness:
                Best_specimen = Best_specimen_an

        print ("Best in Africe    ", Best_specimen_af.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen_af.workers)
        print ("Best in Eurasii   ", Best_specimen_eu.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen_eu.workers)
        print ("Best in Australii ", Best_specimen_au.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen_au.workers)
        print ("Best in Americe   ", Best_specimen_am.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen_am.workers)
        print ("Best in Antarktis ", Best_specimen_an.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen_an.workers)
        print ("Best globaly      ", Best_specimen.fitness, " from ", Theoretical_fitness*len(workers_sources), Best_specimen.workers)

        Population_af = generate_population(hat_selekce_af,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_af) 
        Population_eu = generate_population(hat_selekce_eu,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_eu) 
        Population_au = generate_population(hat_selekce_au,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_au) 
        Population_am = generate_population(hat_selekce_am,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_am) 
        Population_an = generate_population(hat_selekce_an,PopulationSize,MutationRate,kalendar_source, first_day, Best_specimen_an) 
        
        u += 1

    print ("")

    rating_af = fin_entity_fitness(workers_sources, Best_specimen_af, kalendar_source, first_day, ideal_fridays ) 
    rating_eu = fin_entity_fitness(workers_sources, Best_specimen_eu, kalendar_source, first_day, ideal_fridays )
    rating_au = fin_entity_fitness(workers_sources, Best_specimen_au, kalendar_source, first_day, ideal_fridays )
    rating_am = fin_entity_fitness(workers_sources, Best_specimen_am, kalendar_source, first_day, ideal_fridays )
    rating_an = fin_entity_fitness(workers_sources, Best_specimen_an, kalendar_source, first_day, ideal_fridays )

    results = {"af":rating_af,"eu":rating_eu,"au":rating_au,"am":rating_am,"an":rating_an} 
    max = max(results, key=results.get)

    if max == "af":
        Best_specimen = Best_specimen_af
    if max == "eu":
        Best_specimen = Best_specimen_eu
    if max == "au":
        Best_specimen = Best_specimen_au
    if max == "am":
        Best_specimen = Best_specimen_am
    if max == "an":
        Best_specimen = Best_specimen_an

    print ("Final.", Best_specimen.workers)
    test = fin_entity_fitness(workers_sources, Best_specimen, kalendar_source, first_day, ideal_fridays)

    # Generate the final calendar based on the very best specimen
    zz = 0
    while zz < len(Best_specimen.workers):
        current_date = first_day + timedelta(days = zz)
        current_date = current_date.strftime('%Y-%m-%d')

        for key in workers_sources:
            if workers_sources[key].letter == Best_specimen.workers[zz]:
                kalendar_source[current_date].worker = key
        
        zz += 1
    

    # Print to screen
    print ("          ", end = " ")
    for key in workers_sources:
        print (key[:3], end=" ")
    print("")
    for day in kalendar_source:
        print (day, end= " ")
        for key in workers_sources:
            if key == kalendar_source[day].worker:
                print (" X ", end = " ")
                if workers_sources[key].letter not in kalendar_source[day].possible_duty:
                    print ("Hard limit error")
            else:
                print ("   ", end = " ")
        print (" ")

    #Notes for the human which can not be implemented via a strict YES or NO setting
    print("Kocmanova desires v Zari jen dve duties")
    print("Rambo nedesires v Cervenci a Srpnu duties")
    print("Skach desires co nejvic sluzeb mezi 2 a 12 srpnem")

    save_results(kalendar_source)