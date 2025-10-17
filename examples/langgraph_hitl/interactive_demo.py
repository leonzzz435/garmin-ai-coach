"""
Interactive LangGraph HITL Demo — inline tools (no ToolNode)
"""

import os
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

# --- Tool: ask_human ---
class AskHumanInput(BaseModel):
    question: str = Field(..., description="The question to ask the human user")

@tool("ask_human", args_schema=AskHumanInput)
def ask_human_tool(question: str) -> str:
    """Ask the human for clarification and return their answer as plain text."""
    reply = interrupt({"type": "ask_human", "question": question})
    return reply.get("content", "No response provided")

# --- Agent node with inline tool execution ---
def agent_node(state: MessagesState):
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([ask_human_tool])

    system_msg = (
        "You are a helpful research assistant. "
        "If the user's request is vague or missing key details, call the ask_human tool. "
        "Ask ONE question at a time. Once you have enough info, give a clear answer."
    )

    # Build dialogue
    messages = [{"role": "system", "content": system_msg}] + state["messages"]

    # First LLM turn
    ai = llm.invoke(messages)

    # If the model decided to call a tool, run it here (inline)
    tool_calls = getattr(ai, "tool_calls", None)
    if tool_calls:
        # We enforce ONE question-at-a-time; take the first call.
        call = tool_calls[0]
        name = call["name"]
        args = call["args"]
        call_id = call["id"]

        if name == "ask_human":
            # This may interrupt; upon resume it returns the human's content.
            tool_result = ask_human_tool.invoke(args)
            tool_msg = ToolMessage(content=tool_result, tool_call_id=call_id)

            # Continue the conversation now that we have the human’s answer
            messages = messages + [ai, tool_msg]
            ai2 = llm.invoke(messages)

            # Return only new messages; MessagesState appends via reducer
            return {"messages": [ai, tool_msg, ai2]}

    # No tools called, just return the LLM message
    return {"messages": [ai]}

# --- Graph (no ToolNode needed) ---
def create_workflow():
    g = StateGraph(MessagesState)
    g.add_node("agent", agent_node)
    g.add_edge(START, "agent")
    g.add_edge("agent", END)
    return g.compile(checkpointer=MemorySaver())

# --- Interactive CLI driver (unchanged, but with robust interrupt handling) ---
def main():
    print("=" * 70)
    print("🤖 Interactive LangGraph HITL Demo (inline tools)")
    print("=" * 70)

    app = create_workflow()
    thread_id = "interactive-session"
    config = {"configurable": {"thread_id": thread_id}}

    user_input = input("\n👤 You: ").strip()
    if user_input.lower() in ["quit", "exit"]:
        print("\nGoodbye!")
        return

    state = {"messages": [HumanMessage(content=user_input)]}

    while True:
        try:
            result = app.invoke(state, config=config)

            # Handle interrupt payloads (list or single payload, depending on version)
            payload = result.get("__interrupt__")
            if payload:
                if isinstance(payload, list) and payload:
                    payload = payload[0]
                value = getattr(payload, "value", payload)
                question = value.get("question", "Question not found")

                print(f"\n🤖 Agent: {question}")
                user_response = input("\n👤 You: ").strip()
                if user_response.lower() in ["quit", "exit"]:
                    print("\nGoodbye!")
                    return

                # Resume the paused graph with the human’s answer
                state = Command(resume={"content": user_response})
                continue  # next loop invokes with the Command

            # Completed turn
            final_message = result["messages"][-1]
            if hasattr(final_message, "content"):
                print(f"\n🤖 Agent: {final_message.content}")

            print("\n" + "=" * 70)
            if input("\nContinue conversation? (yes/no): ").strip().lower() not in ["yes", "y"]:
                print("\nGoodbye!")
                return

            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ["quit", "exit"]:
                print("\nGoodbye!")
                return

            # With a checkpointer, passing only the new HumanMessage is fine;
            # it appends to the saved thread.
            state = {"messages": [HumanMessage(content=user_input)]}

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye!")
            return
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback; traceback.print_exc()
            return

if __name__ == "__main__":
    main()
