#!/usr/bin/env python
from crewai.flow import Flow, listen, start
from workflow.crews.test_crew.test_crew import TestCrew
from workflow.state.test_state import TestState


class TestFlow(Flow[TestState]):
    @start()
    def generate_sentence_count(self):
        print("Running Test Flow")

    @listen(generate_sentence_count)
    def run_test(self):
        print(f"Generating a short text about:", self.state.subject)
        result = TestCrew().crew().kickoff(inputs={"subject": self.state.subject})

        print("Short text generated:", result.raw)
        self.state.result = result.raw

        return result.raw


def kickoff(inputs: dict | None = None):
    test_flow = TestFlow()
    return test_flow.kickoff(inputs=inputs)


if __name__ == "__main__":
    kickoff()
