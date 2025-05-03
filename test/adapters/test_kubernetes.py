import pytest

from ballista.types import Bolt


@pytest.fixture
def bolt(request):
    return {"test1": None}[request.param]


example_bolts = pytest.mark.parametrize("bolt", ["test1"], indirect=["bolt"])


@example_bolts
def test_resource_generation(bolt: Bolt):
    print(bolt)
