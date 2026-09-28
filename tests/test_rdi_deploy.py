import httpx
import pytest

from scripts.rdi_deploy import deploy


SECRETS = {
    "sqlserver": {"USERNAME": "cdc", "PASSWORD": "source-private"},
    "target": {"USERNAME": "default", "PASSWORD": "target-private"},
}


def test_secret_scope_and_reload_retry():
    requests = []
    sleeps = []
    validations = 0

    def handler(request):
        nonlocal validations
        requests.append(request)
        if "/secrets" in request.url.path:
            return httpx.Response(409 if request.method == "POST" else 200)
        if request.url.params.get("dry_run") == "true":
            validations += 1
            if validations == 1:
                return httpx.Response(400, text="Login failed for ${SQLSERVER_DB_USERNAME}")
        return httpx.Response(200)

    with httpx.Client(base_url="https://rdi.test", transport=httpx.MockTransport(handler)) as client:
        deploy(client, {"jobs": []}, SECRETS, sleep=sleeps.append)
    assert validations == 2
    assert sleeps == [5]
    secret_requests = [r for r in requests if "/secrets" in r.url.path]
    assert {r.url.params["db"] for r in secret_requests} == {"sqlserver", "target"}
    assert requests[-1].url.params["dry_run"] == "false"


def test_validation_errors_are_redacted_and_prevent_deployment():
    requests = []

    def handler(request):
        requests.append(request)
        if "/secrets" in request.url.path:
            return httpx.Response(200)
        return httpx.Response(400, text="private password source-private, invalid job")

    with httpx.Client(base_url="https://rdi.test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="Pipeline validation failed") as error:
            deploy(client, {}, SECRETS)
    assert "source-private" not in str(error.value)
    assert all(r.url.params.get("dry_run") != "false" for r in requests)


def test_secret_propagation_wait_is_bounded():
    def handler(request):
        return httpx.Response(200) if "/secrets" in request.url.path else httpx.Response(503)

    with httpx.Client(base_url="https://rdi.test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="HTTP 503"):
            deploy(client, {}, SECRETS, wait_seconds=0)


def test_reject_full_secret_names_before_mutations():
    with httpx.Client(base_url="https://rdi.test") as client:
        with pytest.raises(ValueError):
            deploy(client, {}, {"sqlserver": {"SQLSERVER_DB_USERNAME": "wrong"}})
