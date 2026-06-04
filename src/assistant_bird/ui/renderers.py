"""Custom Chainlit element renderers for Assistant-Bird."""

import chainlit as cl


async def render_agent_switch(agent_name: str, task: str = "") -> None:
    """Display which agent is currently active.

    Args:
        agent_name: The name of the active agent.
        task: Optional task description.
    """
    step = cl.Step(name=agent_name, type="assistant")
    if task:
        step.description = task
    await step.send()


async def render_tool_call(tool_name: str, tool_input: dict, tool_output: str = "") -> None:
    """Render a tool call as an expandable step.

    Args:
        tool_name: The name of the tool being called.
        tool_input: The input parameters.
        tool_output: The output result.
    """
    step = cl.Step(name=f"🔧 {tool_name}", type="tool")
    step.input = str(tool_input)
    if tool_output:
        step.output = tool_output
    await step.send()
