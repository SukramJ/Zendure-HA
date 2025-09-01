"""Module for the Solarflow2400AC device integration in Home Assistant."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.zendure_ha.device import ZendureZenSdk

_LOGGER = logging.getLogger(__name__)


class SolarFlow2400AC(ZendureZenSdk):
    def __init__(self, hass: HomeAssistant, deviceId: str, prodName: str, definition: Any) -> None:
        """Initialise SolarFlow2400AC."""
        super().__init__(hass, deviceId, definition["deviceName"], prodName, definition)
        self.maxDischarge = 2400
        self.maxCharge = -2400
        self.maxSolar = -2400
