from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("livekit")

from agent import ALLOWED_ACTIONS, Assistant

pytestmark = pytest.mark.asyncio


@pytest.fixture
def assistant():
    return Assistant()


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.session.tts.update_options = MagicMock()
    return ctx


class TestVehicleAction:
    async def test_allowed_action_returns_success(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await assistant.vehicle_action(mock_context, action="ac_on", parameters={})

        assert result == "Executed ac_on"

    async def test_sends_correct_payload(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_post = mock_client.return_value.__aenter__.return_value.post
            mock_post.return_value = mock_response

            await assistant.vehicle_action(
                mock_context, action="set_level", parameters={"level": 3}
            )

        mock_post.assert_called_once_with(
            "https://yaquod-agent.fastapicloud.dev/api/vehicle/action",
            json={
                "vehicle_id": "vehicle_001",
                "action": "set_level",
                "parameters": {"level": 3},
            },
        )

    async def test_disallowed_action_is_rejected(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            result = await assistant.vehicle_action(
                mock_context, action="accelerate", parameters={}
            )

        assert result == "This action is not allowed."
        mock_client.assert_not_called()

    async def test_api_error_response(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await assistant.vehicle_action(mock_context, action="ac_on", parameters={})

        assert result == "Vehicle API error"

    async def test_network_error(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = Exception(
                "Connection refused"
            )

            result = await assistant.vehicle_action(mock_context, action="ac_on", parameters={})

        assert result == "Vehicle system unavailable"

    async def test_none_parameters_defaults_to_empty(self, assistant, mock_context):
        with patch("httpx2.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_post = mock_client.return_value.__aenter__.return_value.post
            mock_post.return_value = mock_response

            await assistant.vehicle_action(mock_context, action="ac_on", parameters=None)

        mock_post.assert_called_once_with(
            "https://yaquod-agent.fastapicloud.dev/api/vehicle/action",
            json={"vehicle_id": "vehicle_001", "action": "ac_on", "parameters": {}},
        )

    async def test_all_allowed_actions_are_accepted(self, assistant, mock_context):
        for action in ALLOWED_ACTIONS:
            with patch("httpx2.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.is_success = True
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                result = await assistant.vehicle_action(mock_context, action=action)
            assert result == f"Executed {action}", f"Failed for action: {action}"


class TestSwitchLanguage:
    async def test_switch_to_valid_language(self, assistant, mock_context):
        result = await assistant.switch_language(mock_context, language="en")

        assert result == "Switched to en"
        mock_context.session.tts.update_options.assert_called_once()

    async def test_switch_to_same_language(self, assistant, mock_context):
        await assistant.switch_language(mock_context, language="ar")

        result = await assistant.switch_language(mock_context, language="ar")

        assert result == "Already using ar"

    async def test_unsupported_language(self, assistant, mock_context):
        result = await assistant.switch_language(mock_context, language="fr")

        assert result == "Unsupported language 'fr'. Supported: ar, en."
        mock_context.session.tts.update_options.assert_not_called()


class TestSearchNearbyPlaces:
    async def test_missing_api_key(self, assistant, mock_context):
        with patch("agent.GOOGLE_MAPS_API_KEY", ""):
            result = await assistant.search_nearby_places(mock_context, query="coffee")
        assert "API key not configured" in result

    async def test_location_fetch_fails(self, assistant, mock_context):
        with (
            patch("agent.GOOGLE_MAPS_API_KEY", "test_key"),
            patch("httpx2.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get.side_effect = Exception(
                "Network error"
            )
            result = await assistant.search_nearby_places(mock_context, query="coffee")
        assert "Unable to get vehicle location" in result

    async def test_successful_search_returns_formatted_results(self, assistant, mock_context):
        mock_places_response = {
            "places": [
                {
                    "displayName": {"text": "Starbucks"},
                    "formattedAddress": "123 Main St",
                    "rating": 4.5,
                    "currentOpeningHours": {"openNow": True},
                },
                {
                    "displayName": {"text": "Local Cafe"},
                    "formattedAddress": "456 Oak Ave",
                    "rating": 4.2,
                    "currentOpeningHours": {"openNow": False},
                },
            ]
        }
        with (
            patch("agent.GOOGLE_MAPS_API_KEY", "test_key"),
            patch("httpx2.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get.return_value = MagicMock(
                is_success=True,
                json=lambda: {"vehicle_id": "vehicle_001", "lat": 30.0444, "lng": 31.2357},
            )
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=200, json=lambda: mock_places_response
            )
            result = await assistant.search_nearby_places(mock_context, query="coffee")
        assert "Starbucks" in result
        assert "Local Cafe" in result
        assert "Open" in result
        assert "Closed" in result
        assert "Rating: 4.5" in result

    async def test_no_results_found(self, assistant, mock_context):
        with (
            patch("agent.GOOGLE_MAPS_API_KEY", "test_key"),
            patch("httpx2.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get.return_value = MagicMock(
                is_success=True,
                json=lambda: {"vehicle_id": "vehicle_001", "lat": 30.0444, "lng": 31.2357},
            )
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=200, json=lambda: {"places": []}
            )
            result = await assistant.search_nearby_places(mock_context, query="nonexistent")
        assert "No results found" in result

    async def test_api_error_returns_graceful_message(self, assistant, mock_context):
        with (
            patch("agent.GOOGLE_MAPS_API_KEY", "test_key"),
            patch("httpx2.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get.return_value = MagicMock(
                is_success=True,
                json=lambda: {"vehicle_id": "vehicle_001", "lat": 30.0444, "lng": 31.2357},
            )
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=500
            )
            result = await assistant.search_nearby_places(mock_context, query="coffee")
        assert "failed" in result or "unavailable" in result
