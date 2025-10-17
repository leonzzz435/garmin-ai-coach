"""
Simple LangGraph example with ask_human as a tool that agents can call.

This demonstrates:
1. ask_human as a LangChain tool that AI agents can decide to use
2. The model decides when it needs human input
3. Using interrupt() within the tool to pause
4. Resuming with Command(resume=...)

This version properly handles the message flow after resume.
"""

import os
from typing import Annotated
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


# --- Tool Definition: ask_human ---
class AskHumanInput(BaseModel):
    """Input schema for ask_human tool"""
    question: str = Field(..., description="The question to ask the human user")


@tool("ask_human", args_schema=AskHumanInput)
def ask_human_tool(question: str) -> str:
    """
    Ask a human user for information or clarification.
    
    Use this tool when you need information from the user or need clarification.
    The workflow will pause and wait for human input before continuing.
    
    Args:
        question: The specific question to ask the user
    
    Returns:
        The human's response as a string
    """
    print(f"\n🔔 Agent is asking: {question}")
    print("   [Workflow paused - waiting for human input...]")
    
    # Interrupt and wait for human response  
    reply = interrupt({
        "type": "ask_human",
        "question": question
    })
    
    # When resumed, return the human's answer
    answer = reply.get("content", "No response provided")
    print(f"   [Received: {answer}]")
    return answer


# --- Agent Node ---
def agent_node(state: MessagesState):
    """Agent that can decide to ask human for clarification."""
    from langchain_openai import ChatOpenAI
    
    # Agent with access to ask_human tool
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools([ask_human_tool])
    
    # System message
    system_msg = """You are a helpful research assistant. 

If the user's request is vague or missing key details, use the ask_human tool to get clarification.
Be specific and concise in your questions.

Once you have enough information, provide a clear, direct answer."""
    
    # Get messages and add system message
    messages = [{"role": "system", "content": system_msg}] + state["messages"]
    
    # Call the LLM
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}


# --- Routing ---
def should_continue(state: MessagesState) -> str:
    """Route based on whether agent called tools or is done"""
    last_message = state["messages"][-1]
    
    # If the agent called tools, execute them
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Otherwise, we're done
    return END


# --- Graph Construction ---
def create_tool_based_hitl_workflow():
    """Create workflow where agents can call ask_human as a tool."""
    
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    # Use built-in ToolNode for proper message handling
    workflow.add_node("tools", ToolNode([ask_human_tool]))
    
    # Define flow
    workflow.add_edge(START, "agent")
    
    # Agent can call tools or end
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # Tools go back to agent (to process tool results)
    workflow.add_edge("tools", "agent")
    
    # Compile with checkpointer (required for interrupts)
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app


# --- Interactive Usage ---
def main_interactive():
    """
    Demonstrate the HITL pattern interactively.
    Shows how to handle interrupts and resume.
    """
    print("=" * 70)
    print("LangGraph HITL Example - Interactive Mode")
    print("=" * 70)
    print("\nThe AI agent will decide when to ask for human input.")
    print("When it does, the workflow will pause.\n")
    
    # Create workflow
    app = create_tool_based_hitl_workflow()
    
    # Unique thread for this conversation
    thread_id = "demo-interactive-thread"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initial user request (intentionally vague to trigger ask_human)
    print("[Starting] User makes a vague request...")
    initial_state = {
        "messages": [
            HumanMessage(content="I need a market analysis. Can you help?")
        ]
    }
    
    print("\n" + "=" * 70)
    
    # First invocation - will interrupt
    try:
        result = app.invoke(initial_state, config=config)
        
        # Check if we hit an interrupt
        if "__interrupt__" in result:
            interrupt_list = result["__interrupt__"]
            interrupt_obj = interrupt_list[0]
            interrupt_value = interrupt_obj.value if hasattr(interrupt_obj, 'value') else interrupt_obj
            
            print("\n" + "=" * 70)
            print("✋ WORKFLOW PAUSED - Human input required!")
            print("=" * 70)
            print(f"\nQuestion: {interrupt_value.get('question')}")
            print("\nTo resume, run:")
            print("  app.invoke(Command(resume={'content': 'your answer'}), config)")
            print("\n" + "=" * 70)
            
            # For demo purposes, simulate a resume
            print("\n[Demo] Simulating resume with answer...")
            human_answer = {
                "content": "Analyze the German renewable energy market for Q1-Q2 2024, focusing on solar and wind."
            }
            print(f"Answer: {human_answer['content']}")
            
            # Resume the workflow
            print("\n[Resuming workflow...]")
            print("=" * 70)
            result = app.invoke(Command(resume=human_answer), config=config)
        
        # Check for second interrupt (in case agent asks another question)
        if "__interrupt__" in result:
            interrupt_list = result["__interrupt__"]
            interrupt_obj = interrupt_list[0]
            interrupt_value = interrupt_obj.value if hasattr(interrupt_obj, 'value') else interrupt_obj
            
            print("\n" + "=" * 70)
            print("✋ SECOND INTERRUPT - Another question!")
            print("=" * 70)
            print(f"\nQuestion: {interrupt_value.get('question')}")
            print("\nFor this demo, we'll stop here.")
            print("In a real app, you'd handle this the same way.")
            return
        
        # Final output
        print("\n" + "=" * 70)
        print("✅ Workflow Complete!")
        print("=" * 70)
        
        # Show final messages
        if "messages" in result:
            print("\nFinal conversation:")
            for i, msg in enumerate(result["messages"], 1):
                role = msg.__class__.__name__
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                content_preview = content[:200] + "..." if len(content) > 200 else content
                print(f"\n  {i}. [{role}]")
                print(f"     {content_preview}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


# --- Programmatic Usage Example ---
def example_programmatic_usage():
    """
    Example showing how to use this in a real application.
    """
    print("\n" + "=" * 70)
    print("Example: Programmatic Usage Pattern")
    print("=" * 70)
    
    code_example = '''
# In your application (e.g., FastAPI endpoint, CLI, etc.)
from langgraph.types import Command
from langchain_core.messages import HumanMessage

app = create_tool_based_hitl_workflow()
thread_id = f"user-{user_id}-{session_id}"
config = {"configurable": {"thread_id": thread_id}}

# 1. Initial request
result = app.invoke(
    {"messages": [HumanMessage(content=user_input)]},
    config=config
)

# 2. Check for interrupt
if "__interrupt__" in result:
    interrupt_obj = result["__interrupt__"][0]
    interrupt_value = interrupt_obj.value
    question = interrupt_value.get("question")
    
    # Save state, show question to user (via UI/Slack/etc.)
    # ... wait for user response ...
    
    # When user responds:
    result = app.invoke(
        Command(resume={"content": user_response}),
        config=config
    )

# 3. Process final result
final_answer = result["messages"][-1].content
print(final_answer)
'''
    
    print(code_example)


if __name__ == "__main__":
    main_interactive()
    example_programmatic_usage()