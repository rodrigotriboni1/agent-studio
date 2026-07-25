"""Foundation smoke tests: the four seams + manifest contract.

These must stay green through every ralph iteration — they lock the seam
contracts the whole build depends on.
"""

from core.manifest import AgentManifest, ManifestStatus
from seams import (
    AllowAllAuthzProvider,
    EchoModelProvider,
    InMemoryToolProvider,
    ManifestAuthzProvider,
    Message,
    ResourceType,
    TenantContext,
    ToolSpec,
    current_tenant,
    use_tenant,
)


def test_tenant_context_namespacing_and_ambient():
    ctx = TenantContext(tenant_id="acme")
    assert ctx.namespaced("agents") == "acme:agents"
    assert current_tenant().tenant_id == "default"
    with use_tenant(ctx):
        assert current_tenant().tenant_id == "acme"
    assert current_tenant().tenant_id == "default"


def test_echo_model_provider_is_offline_deterministic():
    provider = EchoModelProvider()
    resp = provider.complete(
        model="echo", messages=[Message(role="user", content="hello")]
    )
    assert resp.content == "[echo] hello"


def test_in_memory_tool_provider_roundtrip():
    tools = InMemoryToolProvider()
    tools.register(
        ToolSpec(name="add", description="add two ints"),
        lambda a, b: a + b,
    )
    assert [t.name for t in tools.list_tools()] == ["add"]
    assert tools.invoke("add", {"a": 2, "b": 3}).content == 5
    assert tools.invoke("missing", {}).is_error


def test_manifest_authz_enforces_allow_list():
    authz = ManifestAuthzProvider()
    allow = {"search", "calc"}
    assert authz.check(
        resource_type=ResourceType.TOOL, resource="search", manifest_allow=allow
    ).allowed
    assert not authz.check(
        resource_type=ResourceType.TOOL, resource="danger", manifest_allow=allow
    ).allowed
    # no allow-list declared ⇒ allow (v0 default)
    assert authz.check(
        resource_type=ResourceType.TOOL, resource="anything", manifest_allow=None
    ).allowed


def test_allow_all_authz_is_permissive():
    authz = AllowAllAuthzProvider()
    assert authz.check(
        resource_type=ResourceType.MODEL, resource="whatever", manifest_allow={"x"}
    ).allowed


def test_manifest_governance_helpers():
    m = AgentManifest(
        id="a1",
        tenant_id="default",
        name="Support",
        model="gpt-4o-mini",
        allowed_tools=["search"],
    )
    assert m.status is ManifestStatus.DRAFT
    assert "gpt-4o-mini" in m.allowed_model_set()
    assert m.allowed_tool_set() == {"search"}
    assert not m.is_published()
