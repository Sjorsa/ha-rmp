from __future__ import annotations
import asyncio
import re
import traceback
from typing import Any
import datetime as dt
from urllib.parse import quote

from homeassistant.components.media_player import (
    _LOGGER,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)

from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.media_player.const import MediaClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,) -> None:
    """Set up the rmp platform."""
    async_add_entities([RMPMediaPlayerEntity(host=entry.data['host'], port=entry.data['port'])])


class RMPMediaPlayerEntity(MediaPlayerEntity):
    """Representation of the Mopidy server."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    _attr_consume_mode: bool | None = None
    _url: str

    def __init__(self, host, port) -> None:
        """Initialize the rmp device."""
        self._attr_supported_features = \
            MediaPlayerEntityFeature.PAUSE | \
            MediaPlayerEntityFeature.SEEK | \
            MediaPlayerEntityFeature.NEXT_TRACK | \
            MediaPlayerEntityFeature.STOP | \
            MediaPlayerEntityFeature.PLAY | \
            MediaPlayerEntityFeature.BROWSE_MEDIA

        self._url = f"http://{host}:{port}"
        self._attr_name = 'Raphson Playback Server'

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        # self.speaker.clear_queue()

    def media_next_track(self) -> None:
        """Send next track command."""
        requests.post(f"{self._url}/next", timeout=5).raise_for_status()

    def media_pause(self) -> None:
        """Send pause command."""
        requests.post(f"{self._url}/pause", timeout=5).raise_for_status()

    def media_play(self) -> None:
        """Send play command."""
        requests.post(f"{self._url}/play", timeout=5).raise_for_status()

    # def media_previous_track(self) -> None:
    #     """Send previous track command."""

    def media_seek(self, position) -> None:
        """Send seek command."""
        requests.post(f"{self._url}/seek", timeout=5, data=str(int(position)).encode()).raise_for_status()

    def media_stop(self) -> None:
        """Send stop command."""
        requests.post(f"{self._url}/stop", timeout=5).raise_for_status()

    # def set_repeat(self, repeat) -> None:
    #     """Set repeat mode."""
    #     self.speaker.set_repeat_mode(repeat)

    # def set_shuffle(self, shuffle) -> None:
    #     """Enable/disable shuffle mode."""
    #     self.speaker.set_shuffle(shuffle)

    # def set_volume_level(self, volume) -> None:
    #     """Set volume level, range 0..1."""
    #     self.speaker.set_volume(int(volume * 100))

    # def volume_down(self) -> None:
    #     """Turn volume down for media player."""
    #     self.speaker.volume_down()

    # def volume_up(self) -> None:
    #     """Turn volume up for media player."""
    #     self.speaker.volume_up()

    # @property
    # def device_info(self) -> dict[str, Any]:
    #     """Return device information about this entity."""
    #     return {
    #         # "identifiers": {(DOMAIN, self.device_name)},
    #         "manufacturer": "Raphson",
    #         # "model": "RMP server",
    #         # "name": self.device_name,
    #         # "sw_version": self.speaker.software_version,
    #     }


    # @property
    # def repeat(self) -> RepeatMode | str | None:
    #     """Return current repeat mode."""
    #     if self.speaker is None:
    #         return None
    #     else:
    #         return self.speaker.repeat

    # @property
    # def supported_features(self) -> MediaPlayerEntityFeature:
    #     """Flag media player features that are supported."""
    #     if self.speaker is None:
    #         return None
    #     else:
    #         return self.speaker.features

    # @property
    # def unique_id(self) -> str:
    #     """Return the unique id for the entity."""
    #     return self.device_uuid

    def update(self) -> None:
        """Get the latest data and update the state."""
        try:
            response = requests.get(f"{self._url}/state", timeout=5)
            response.raise_for_status()
            self._attr_available = True
        except:
            _LOGGER.error(f"{self.entity_id} is unavailable")
            self._attr_available = False
            return

        state = response.json()
        self._attr_media_position = state["player"]["position"]
        self._attr_media_position_updated_at = dt.datetime.now()
        self._attr_media_duration = state["player"]["duration"]

        volume_level = state["player"]["volume"]/100
        if volume_level >= 0:
            self._attr_volume_level = volume_level
        else:
            self._attr_volume_level = 0

        # Hier misschien nog meer
        if state["player"]["is_playing"]:
            self._attr_state = MediaPlayerState.PLAYING
        else:
            self._attr_state = MediaPlayerState.PAUSED


        if state["currently_playing"]:
            self._attr_media_content_id = state["currently_playing"]["path"]
            self._attr_media_title = state["currently_playing"]["title"]
            self._attr_media_album_name = state["currently_playing"]["album"]
            self._attr_media_album_artist = state["currently_playing"]["album_artist"]
            self._attr_media_artist = ', '.join(state["currently_playing"]["artists"])

            self._attr_media_image_url = f"{self._url}/image#{quote(state["currently_playing"]["path"])}"
        else:
            self._attr_media_content_id = None
            self._attr_media_title = None
            self._attr_media_album_name = None
            self._attr_media_album_artist = None
            self._attr_media_artist = None
            self._attr_media_image_url = None

    async def async_browse_media(
            self,
            media_content_type: MediaType | str | None = None,
            media_content_id: str | None = None,
        ) -> BrowseMedia:
            if media_content_type == None or media_content_type == MediaType.APP:
                def retrieve_playlists() -> list[str]:
                    response = requests.get(f'{self._url}/state', timeout=5)
                    response.raise_for_status()
                    return response.json()['playlists']['all']
                playlists = await asyncio.get_running_loop().run_in_executor(None, retrieve_playlists)
                children = [BrowseMedia(media_class=MediaClass.PLAYLIST,
                                        media_content_id=playlist,
                                        media_content_type=MediaType.PLAYLIST,
                                        title=playlist,
                                        can_play=False,
                                        can_expand=True)
                            for playlist in playlists]
                return BrowseMedia(media_class=MediaClass.APP, media_content_type=MediaType.APP, media_content_id="root", children=children, title="Playlists", can_play=False, can_expand=False)

            if media_content_type == MediaType.PLAYLIST and media_content_id is not None:
                def retrieve_tracks() -> list[str]:
                    response = requests.get(f'{self._url}/list_tracks', params={'playlist': media_content_id}, timeout=5)
                    response.raise_for_status()
                    return response.json()['tracks']
                tracks = await asyncio.get_running_loop().run_in_executor(None, retrieve_tracks)
                children = [BrowseMedia(media_class=MediaClass.TRACK,
                                        media_content_id=track['path'],
                                        media_content_type=MediaType.TRACK,
                                        title=track['display'],
                                        can_play=True,
                                        can_expand=False)
                            for track in tracks]
                return BrowseMedia(media_class=MediaClass.PLAYLIST, media_content_type=MediaType.PLAYLIST, media_content_id=media_content_id, children=children, title="Playlists", can_play=False, can_expand=False)

            raise ValueError(media_content_type, media_content_id)
