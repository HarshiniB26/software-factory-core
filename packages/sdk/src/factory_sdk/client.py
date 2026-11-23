import httpx
from factory_contracts import FactoryRequest, RequestCreate


class FactoryClient:
    def __init__(
        self, base_url: str, client: httpx.Client | None = None, timeout: float = 30
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._owns = client is None

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def __enter__(self) -> "FactoryClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def health(self) -> dict[str, str]:
        response = self._client.get(f"{self._base}/health")
        response.raise_for_status()
        payload = response.json()
        return {str(key): str(value) for key, value in payload.items()}

    def create_request(
        self,
        title: str,
        body: str,
        target: str | None = None,
        requester: str = "local",
    ) -> FactoryRequest:
        payload = RequestCreate(title=title, body=body, target=target, requester=requester)
        response = self._client.post(
            f"{self._base}/requests",
            json=payload.model_dump(mode="json"),
        )
        response.raise_for_status()
        return FactoryRequest.model_validate(response.json())

    def list_requests(self) -> list[FactoryRequest]:
        response = self._client.get(f"{self._base}/requests")
        response.raise_for_status()
        return [FactoryRequest.model_validate(item) for item in response.json()]
