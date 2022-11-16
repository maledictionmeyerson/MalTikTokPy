import pytest
from tiktokapipy.api import TikTokAPI as SyncTikTokAPI
from tiktokapipy.async_api import AsyncTikTokAPI as AsyncTikTokAPI


@pytest.fixture(scope="function")
async def async_api():
    async with AsyncTikTokAPI(data_dump_file="examples/test_data.json") as api:
        yield api


@pytest.fixture(scope="function")
def sync_api():
    with SyncTikTokAPI(data_dump_file="examples/test_data.json") as api:
        yield api


@pytest.fixture(scope="session")
def video_id():
    return 7109512307918621995


@pytest.fixture(scope="session")
def user_name():
    return "tiktok"


@pytest.fixture(scope="session")
def challenge_name():
    return "fyp"
