"""Run against the full candidate package via PYTHONPATH, never patch the running venv."""

import io
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from viser import ClientHandle
from viser import _messages


def encoded(mode="RGB", fmt="JPEG"):
    image = Image.new(mode, (3, 2), (40, 80, 120) if mode == "RGB" else (40, 80, 120, 255))
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


class Connection:
    def __init__(self):
        self.handlers = []
        self.requests = []
        self.on_request = None
        self.condition = threading.Condition()

    def register_handler(self, kind, callback):
        self.handlers.append(callback)

    def unregister_handler(self, kind, callback):
        self.handlers.remove(callback)

    def queue_message(self, message):
        with self.condition:
            self.requests.append(message)
            self.condition.notify_all()
        if self.on_request:
            self.on_request(message)

    def reply(self, request, payload=None, error=None):
        response = _messages.GetRenderResponseMessage(
            encoded() if payload is None else payload, request.render_uuid, error
        )
        for callback in list(self.handlers):
            callback(7, response)


@pytest.fixture
def client():
    handle = ClientHandle.__new__(ClientHandle)
    handle.client_id = 7
    handle.camera = SimpleNamespace(
        position=(1, 2, 3), wxyz=(1, 0, 0, 0), fov=0.9, near=0.002, far=100.0, aspect=1.3333
    )
    handle._websock_connection = Connection()
    handle._viser_server = SimpleNamespace(
        flush=lambda: None,
        _connected_clients={7: handle},
        _websock_server=SimpleNamespace(flush_client=lambda _: None),
    )
    return handle


def test_default_current_projection_and_real_decode(client):
    connection = client._websock_connection
    connection.on_request = connection.reply
    image = client.get_render(2, 3, expected_node_names=("/model",))
    request = connection.requests[0]
    assert (request.near, request.far, request.projection_aspect) == (0.002, 100, 1.3333)
    assert request.expected_node_names == ("/model",)
    assert request.timeout_s == 30.0 and not request.transparent_background
    assert request.fov == 0.9 and request.position == (1, 2, 3)
    assert image.shape == (2, 3, 3) and image.dtype == np.uint8
    assert not connection.handlers


def test_explicit_projection_and_opaque_png(client):
    connection = client._websock_connection
    connection.on_request = lambda req: connection.reply(req, encoded("RGBA", "PNG"))
    image = client.get_render(
        2,
        3,
        position=(4, 5, 6),
        wxyz=(1, 0, 0, 0),
        fov=0.7,
        near=0.004,
        far=33,
        projection_aspect=1.25,
        timeout=2,
        transport_format="png",
        transparent_background=False,
    )
    request = connection.requests[0]
    assert (request.near, request.far, request.projection_aspect) == (0.004, 33, 1.25)
    assert not request.transparent_background
    assert image.shape == (2, 3, 4) and np.all(image[..., 3] == 255)
    assert not connection.handlers


def test_default_png_remains_transparent_request(client):
    connection = client._websock_connection
    connection.on_request = lambda req: connection.reply(req, encoded("RGBA", "PNG"))
    client.get_render(2, 3, transport_format="png")
    assert connection.requests[0].transparent_background


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": None},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"near": 0},
        {"far": 0.001},
        {"projection_aspect": float("nan")},
        {"fov": 0},
        {"wxyz": (0, 0, 0, 0)},
        {"position": (float("nan"), 0, 0)},
        {"expected_node_names": ("model",)},
        {"expected_node_names": ("/a", "/a")},
        {"transparent_background": True},
    ],
)
def test_invalid_request_rejected_before_registration(client, kwargs):
    with pytest.raises(ValueError):
        client.get_render(2, 3, **kwargs)
    assert not client._websock_connection.handlers
    assert not client._websock_connection.requests


def test_timeout_removes_handler(client):
    with pytest.raises(TimeoutError):
        client.get_render(2, 3, timeout=0.02)
    assert not client._websock_connection.handlers


def test_disconnect_and_resource_error(client):
    client._viser_server._connected_clients.clear()
    with pytest.raises(RuntimeError, match="disconnected"):
        client.get_render(2, 3, timeout=1)
    assert not client._websock_connection.handlers
    client._viser_server._connected_clients[7] = client
    client._websock_connection.on_request = lambda req: client._websock_connection.reply(
        req, b"", "GLB texture failed"
    )
    with pytest.raises(RuntimeError, match="GLB texture failed"):
        client.get_render(2, 3)
    assert not client._websock_connection.handlers


def test_queue_failure_and_bad_image_cleanup(client):
    connection = client._websock_connection

    def fail(_):
        raise OSError("queue failed")

    connection.on_request = fail
    with pytest.raises(OSError, match="queue failed"):
        client.get_render(2, 3)
    assert not connection.handlers
    connection.on_request = lambda req: connection.reply(req, b"not an image")
    with pytest.raises(RuntimeError):
        client.get_render(2, 3)
    assert not connection.handlers


def test_concurrent_uuid_response_correlation(client):
    connection = client._websock_connection
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(client.get_render, 2, 3, timeout=2)
        b = pool.submit(client.get_render, 2, 3, timeout=2)
        with connection.condition:
            assert connection.condition.wait_for(lambda: len(connection.requests) == 2, timeout=1)
        assert connection.requests[0].render_uuid != connection.requests[1].render_uuid
        connection.reply(connection.requests[1])
        connection.reply(connection.requests[0])
        assert a.result().shape == b.result().shape == (2, 3, 3)
    assert not connection.handlers
