from pathlib import Path

from cache.keys import tenant_key
from harness.graphs.supervisor import compile_supervisor_graph
from knowledge.file_reader import load_markdown


ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_root_exists() -> None:
    node = load_markdown(ROOT / "knowledge" / "_moc.md")
    assert node["metadata"]["id"] == "knowledge-root"


def test_pack_manifest_exists() -> None:
    manifest = ROOT / "knowledge" / "industry-packs" / "hvac" / "pack.yaml"
    assert manifest.exists()


def test_conflict_resolution_sql_exists() -> None:
    sql = (ROOT / "supabase" / "migrations" / "006_compliance_conflict_resolution.sql").read_text()
    assert "most-restrictive" not in sql.lower() or "deny" in sql.lower()
    assert "resolve_compliance_conflicts" in sql


def test_supervisor_graph_compiles() -> None:
    graph = compile_supervisor_graph()
    assert graph is not None


def test_tenant_cache_keys_are_namespaced() -> None:
    assert tenant_key("a", "pack", "hvac") != tenant_key("b", "pack", "hvac")


def test_worker_spec_tools_are_strings() -> None:
    import json

    worker_spec = json.loads((ROOT / "knowledge" / "worker-specs" / "customer-analyst.yaml").read_text())
    assert all(isinstance(tool, str) for tool in worker_spec["tools_allowed"])
