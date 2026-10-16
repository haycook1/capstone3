
from orchestrator import TOOL_REGISTRY

print("Registered tools:", [tool.name for tool in TOOL_REGISTRY])
for tool in TOOL_REGISTRY:
    print(f"\n{tool.name}:")
    print(tool.description)

