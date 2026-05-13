"""
Tests for agent state schema.
"""

from src.agent.state import AgentState


class TestAgentState:
    def test_create_state(self):
        state: AgentState = {
            "user_message": "Hello",
            "user_id": "U123",
            "channel_id": "C456",
            "conversation_history": [],
            "memory_context": "",
            "rag_context": "",
            "rag_enabled": True,
            "selected_tools": [],
            "tool_results": {},
            "agent_response": "",
            "iteration_count": 0,
            "max_iterations": 5,
        }
        assert state["user_message"] == "Hello"
        assert state["user_id"] == "U123"
        assert state["rag_enabled"] is True
        assert state["max_iterations"] == 5

    def test_state_with_history(self):
        state: AgentState = {
            "user_message": "Summarize",
            "user_id": "U123",
            "channel_id": "C456",
            "conversation_history": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            "memory_context": "Previous project discussions",
            "rag_context": "Relevant past conversation",
            "rag_enabled": True,
            "selected_tools": ["get_channel_messages"],
            "tool_results": {"get_channel_messages": {"messages": []}},
            "agent_response": "",
            "iteration_count": 1,
            "max_iterations": 5,
        }
        assert len(state["conversation_history"]) == 2
        assert len(state["selected_tools"]) == 1
