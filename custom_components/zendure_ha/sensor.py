"""Interfaces with the Zendure Integration api sensors."""

import logging
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .entity import EntityDevice, EntityZendure

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(_hass: HomeAssistant, _config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Zendure sensor."""
    ZendureSensor.add = async_add_entities


class ZendureSensor(EntityZendure, SensorEntity):
    add: AddEntitiesCallback

    def __init__(
        self,
        device: EntityDevice,
        uniqueid: str,
        template: Template | None = None,
        uom: str | None = None,
        deviceclass: Any | None = None,
        stateclass: Any | None = None,
        precision: int | None = None,
        factor: int = 1,
    ) -> None:
        """Initialize a Zendure entity."""
        super().__init__(device, uniqueid, "sensor")
        self.entity_description = SensorEntityDescription(
            key=uniqueid, name=uniqueid, native_unit_of_measurement=uom, device_class=deviceclass, state_class=stateclass
        )
        self._value_template: Template | None = template
        if precision is not None:
            self._attr_suggested_display_precision = precision
        self.factor = factor
        device.call_threadsafe(self.add, [self])

    def update_value(self, value: Any) -> bool:
        try:
            new_value = self._value_template.async_render_with_possible_json_value(value, None) if self._value_template is not None else value
            if self.factor != 1:
                try:
                    new_value = float(new_value) / self.factor
                except ValueError:
                    new_value = 0

            if self.hass and new_value != self._attr_native_value:
                self._attr_native_value = new_value
                if self.hass and self.hass.loop.is_running():
                    self.schedule_update_ha_state()
                return True

        except Exception as err:
            self._attr_native_value = value
            _LOGGER.error(f"Error {err} setting state: {self._attr_unique_id} => {value}")
            _LOGGER.error(traceback.format_exc())
        return False

    @property
    def value(self) -> Any:
        """Return the current value of the sensor."""
        return self._attr_native_value / self.factor if isinstance(self._attr_native_value, (int, float)) else 0


class ZendureRestoreSensor(ZendureSensor, RestoreEntity):
    """Representation of a Zendure sensor entity with restore."""

    def __init__(
        self,
        device: EntityDevice,
        uniqueid: str,
        template: Template | None = None,
        uom: str | None = None,
        deviceclass: Any | None = None,
        stateclass: Any | None = None,
        precision: int | None = None,
    ) -> None:
        """Initialize a select entity."""
        super().__init__(device, uniqueid, template, uom, deviceclass, stateclass, precision)
        self.last_value = 0
        self.lastValueUpdate = dt_util.utcnow()
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state != "unknown":
            self._attr_native_value = state.state
            _LOGGER.debug(f"Restored state for {self.entity_id}: {self._attr_native_value}")

    def aggregate(self, time: datetime, value: Any) -> None:
        # Get the kWh value from the last value and the time since the last update
        value = float(value) if isinstance(value, (int, float)) else 0.0
        if (self.last_reset is None or self.last_reset.date() != time.date()) and self.state_class != "total_increasing":
            self._attr_native_value = 0.0
            self._attr_last_reset = time
        else:
            try:
                kWh = self.last_value * (time.timestamp() - self.lastValueUpdate.timestamp()) / 3600000
                self._attr_native_value = kWh + float(self.state)
            except Exception as e:
                _LOGGER.error(f"Unable to connect to Zendure {e}!")

        self.last_value = value
        self.lastValueUpdate = time
        if self.hass and self.hass.loop.is_running():
            self.schedule_update_ha_state()


class ZendureCalcSensor(ZendureSensor):
    """Representation of a Zendure Calculated Sensor."""

    def __init__(
        self,
        device: EntityDevice,
        uniqueid: str,
        calculate: Callable[[Any], Any] | None = None,
        uom: str | None = None,
        deviceclass: Any | None = None,
        stateclass: Any | None = None,
        precision: int | None = None,
    ) -> None:
        """Initialize a Zendure entity."""
        super().__init__(device, uniqueid, None, uom, deviceclass, stateclass, precision)
        self.calculate = calculate

    def update_value(self, value: Any) -> bool:
        try:
            new_value = self._value_template.async_render_with_possible_json_value(value, None) if self._value_template is not None else value

            if self.hass and new_value != self._attr_native_value and self.calculate is not None:
                self._attr_native_value = self.calculate(new_value)
                if self.hass and self.hass.loop.is_running():
                    self.schedule_update_ha_state()
                return True

        except Exception as err:
            self._attr_native_value = value
            _LOGGER.error(f"Error {err} setting state: {self._attr_unique_id} => {value}")
            _LOGGER.error(traceback.format_exc())
        return False

    def calculate_version(self, value: Any) -> Any:
        """Calculate the version from the value."""
        version = int(value)
        version = f"v{(version & 0xF000) >> 12}.{(version & 0x0F00) >> 8}.{version & 0x00FF}" if version != 0 else "not provided"
        if self._attr_translation_key in {"soft_version", "master_soft_version"} and self._attr_device_info is not None:
            self._attr_device_info["sw_version"] = version

        return version
