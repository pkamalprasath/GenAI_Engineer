from src.penn_test_crew_agent import PennTestAgentCrew
from src.travel_agent_crew import TravelAgentCrew


# You can Invoke only one of the two agent. Please comment the code accordingly.
if __name__ == '__main__':
    # Replace with your inputs, it will automatically interpolate any tasks and agents information
    inputs = {
        'origin': 'Philadelphia, PA',
        'destination': 'New York, JFK',
        'age': 7,
        'hotel_location': 'Brooklyn',
        'flight_information': 'GOL 1234, leaving at March 30, 2025, 5:00',
        'trip_duration': '2 days'
    }
    result = TravelAgentCrew().crew().kickoff(inputs=inputs)
    print(result)


if __name__ == '__main__':
    result = PennTestAgentCrew().crew().kickoff()
    print(result)
