"""The four seams that keep ``agent-studio`` pluggable into the platform later
without rewriting the core (spec §4).

    ToolProvider   → MCP client today  → MCP Gateway later
    ModelProvider  → LiteLLM today     → LLM Bridge later
    AuthzProvider  → manifest stub today → OpenFGA/SpiceDB later
    TenantContext  → carried everywhere from commit 1

Program against these interfaces, never against concrete providers.
"""

from seams.authz import (
    AllowAllAuthzProvider,
    AuthzProvider,
    Decision,
    ManifestAuthzProvider,
    ResourceType,
)
from seams.models import (
    EchoModelProvider,
    LiteLLMModelProvider,
    Message,
    ModelProvider,
    ModelResponse,
)
from seams.tenancy import (
    DEFAULT_TENANT_ID,
    TenantContext,
    current_tenant,
    use_tenant,
)
from seams.tools import (
    InMemoryToolProvider,
    MCPToolProvider,
    ToolProvider,
    ToolResult,
    ToolSpec,
)

__all__ = [
    # tenancy
    "TenantContext",
    "DEFAULT_TENANT_ID",
    "current_tenant",
    "use_tenant",
    # models
    "ModelProvider",
    "LiteLLMModelProvider",
    "EchoModelProvider",
    "Message",
    "ModelResponse",
    # tools
    "ToolProvider",
    "MCPToolProvider",
    "InMemoryToolProvider",
    "ToolSpec",
    "ToolResult",
    # authz
    "AuthzProvider",
    "ManifestAuthzProvider",
    "AllowAllAuthzProvider",
    "ResourceType",
    "Decision",
]
