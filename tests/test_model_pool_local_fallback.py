"""Optional local model readiness and cloud fallback behavior."""

from core.model_pool_manager import Model, ModelPoolManager, ModelRoute


def _pool():
    pool = object.__new__(ModelPoolManager)
    local = Model(
        id="local",
        name="local-model",
        provider="local_llama",
        base_url="http://127.0.0.1:8080/v1",
        api_key="local-key",
        enabled=True,
    )
    cloud = Model(
        id="cloud",
        name="cloud-model",
        provider="openai",
        base_url="https://api.example.test/v1",
        api_key="cloud-key",
        enabled=True,
    )
    pool._models = {"local": local, "cloud": cloud}
    pool._routes = {"simple_chat": ModelRoute(task_type="simple_chat", primary="local", secondary="cloud")}
    pool._config = {"models": {"local": {"api_key": "local-key"}, "cloud": {"api_key": "cloud-key"}}}
    return pool


def test_task_route_skips_unavailable_local_model(monkeypatch):
    pool = _pool()
    monkeypatch.setattr(pool, "_probe_local_endpoint", lambda model: model.id != "local")

    assert pool.select_model_for_task("simple_chat").id == "cloud"


def test_direct_local_model_client_uses_cloud_fallback(monkeypatch):
    pool = _pool()
    monkeypatch.setattr(pool, "_probe_local_endpoint", lambda model: model.id != "local")

    from core.ai_client import AIClientFactory

    monkeypatch.setattr(AIClientFactory, "create_client", staticmethod(lambda **kwargs: kwargs))

    client_config = pool.create_ai_client(model_id="local")

    assert client_config["model"] == "cloud-model"
    assert client_config["base_url"] == "https://api.example.test/v1"


def test_local_probe_checks_models_readiness_endpoint(monkeypatch):
    pool = _pool()
    requests = []
    from core import model_pool_manager

    monkeypatch.setitem(model_pool_manager._LOCAL_PROBE_CACHE, "http://127.0.0.1:8080/v1", (0, False))

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        requests.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr("core.model_pool_manager.urlopen", fake_urlopen)
    monkeypatch.setattr(pool, "_maybe_autostart_local", lambda _url: None)

    assert pool._probe_local_endpoint(pool.get_model("local")) is True
    assert requests[0][0] == "http://127.0.0.1:8080/v1/models"
    assert requests[0][1] <= 1
