from __future__ import annotations

import datetime as dt
import logging
from typing import cast, override
from urllib.parse import quote

from aiohttp import ClientSession

from homeassistant.components.media_player import (MediaPlayerDeviceClass,
                                                   MediaPlayerEntity)
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.media_player.const import (
    MediaClass, MediaPlayerEntityFeature, MediaPlayerState, MediaType)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,) -> None:
    """Set up the rmp platform."""
    base_url = f"http://{entry.data['host']}:{entry.data['port']}"
    session = aiohttp_client.async_create_clientsession(hass, base_url=base_url)
    async_add_entities([RMPMediaPlayerEntity(session, base_url)])


class RMPMediaPlayerEntity(MediaPlayerEntity):
    """Representation of the Mopidy server."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    _attr_consume_mode: bool | None = None
    _base_url: str
    _session: ClientSession
    _playlists: list[str]
    _enabled_playlists: list[str]

    def __init__(self, session: ClientSession, base_url: str) -> None:
        """Initialize the rmp device."""
        self._attr_supported_features = \
            MediaPlayerEntityFeature.PAUSE | \
            MediaPlayerEntityFeature.SEEK | \
            MediaPlayerEntityFeature.NEXT_TRACK | \
            MediaPlayerEntityFeature.STOP | \
            MediaPlayerEntityFeature.PLAY | \
            MediaPlayerEntityFeature.BROWSE_MEDIA | \
            MediaPlayerEntityFeature.PLAY_MEDIA | \
            MediaPlayerEntityFeature.VOLUME_SET

        self._base_url = base_url
        self._session = session
        self._attr_unique_id = base_url
        self._attr_name = 'Raphson Playback Server'
        self._playlists = []
        self._enabled_playlists = []

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        response = await self._session.post('/next')
        response.raise_for_status()

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        response = await self._session.post('/pause')
        response.raise_for_status()

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        response = await self._session.post('/play')
        response.raise_for_status()

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        # TODO
        raise NotImplementedError()

    @override
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        response = await self._session.post('/seek', data=str(int(position)).encode())
        response.raise_for_status()

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        response = await self._session.post('/stop')
        response.raise_for_status()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        response = await self._session.post('/volume', data=str(int(volume * 100)).encode())
        response.raise_for_status()

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        try:
            response = await self._session.get(f"/state")
            response.raise_for_status()
            if not self._attr_available:
                _LOGGER.info(f"{self.entity_id} is available")
            self._attr_available = True
        except:
            if self._attr_available:
                _LOGGER.warn(f"{self.entity_id} is unavailable")
            self._attr_available = False
            return

        state = await response.json()

        self._playlists = state['playlists']['all']
        self._enabled_playlists = state['playlists']['enabled']

        self._attr_media_position = state["player"]["position"]
        self._attr_media_position_updated_at = dt.datetime.now()
        self._attr_media_duration = state["player"]["duration"]

        volume_level = state["player"]["volume"] / 100
        if volume_level >= 0:
            self._attr_volume_level = volume_level
        else:
            self._attr_volume_level = 0

        if not state["player"]["has_media"]:
            self._attr_state = MediaPlayerState.IDLE
        elif state["player"]["is_playing"]:
            self._attr_state = MediaPlayerState.PLAYING
        else:
            self._attr_state = MediaPlayerState.PAUSED

        if state["currently_playing"]:
            path: str = state["currently_playing"]["path"]
            self._attr_media_content_id = path
            self._attr_media_content_type = MediaType.TRACK
            self._attr_media_title = state["currently_playing"]["title"]
            self._attr_media_album_name = state["currently_playing"]["album"]
            self._attr_media_album_artist = state["currently_playing"]["album_artist"]
            self._attr_media_artist = ', '.join(cast(list[str], state["currently_playing"]["artists"]))
            self._attr_media_playlist = path[:path.index('/')]
            self._attr_media_image_url = f"{self._base_url}/image#{quote(state["currently_playing"]["path"])}"
        else:
            self._attr_media_content_id = None
            self._attr_media_content_type = None
            self._attr_media_title = None
            self._attr_media_album_name = None
            self._attr_media_album_artist = None
            self._attr_media_artist = None
            self._attr_media_playlist = None
            self._attr_media_image_url = None

    @override
    async def async_browse_media(
            self,
            media_content_type: MediaType | str | None = None,
            media_content_id: str | None = None,
        ) -> BrowseMedia:
            if media_content_type == None or media_content_type == MediaType.APP:
                children = [BrowseMedia(media_class=MediaClass.PLAYLIST,
                                        media_content_id=playlist,
                                        media_content_type=MediaType.PLAYLIST,
                                        title=playlist + ('✓' if playlist in self._enabled_playlists else ''),
                                        can_play=True,
                                        can_expand=True)
                            for playlist in self._playlists]

                # News
                children.append(BrowseMedia(media_class=MediaClass.PODCAST,
                                        media_content_id="news",
                                        media_content_type=MediaType.PODCAST,
                                        title="News",
                                        can_play=True,
                                        can_expand=False))

                return BrowseMedia(media_class=MediaClass.APP, media_content_type=MediaType.APP, media_content_id="root", children=children, title="Playlists", can_play=False, can_expand=False)

            if media_content_type == MediaType.PLAYLIST and media_content_id is not None:
                response = await self._session.get(f'/list_tracks', params={'playlist': media_content_id})
                response.raise_for_status()
                tracks = (await response.json())['tracks']
                children = [BrowseMedia(media_class=MediaClass.TRACK,
                                        media_content_id=track['path'],
                                        media_content_type=MediaType.TRACK,
                                        title=track['display'],
                                        can_play=True,
                                        can_expand=False)
                            for track in tracks]
                return BrowseMedia(media_class=MediaClass.PLAYLIST, media_content_type=MediaType.PLAYLIST, media_content_id=media_content_id, children=children, title=media_content_id, can_play=False, can_expand=False)

            raise ValueError(media_content_type, media_content_id)

    @override
    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs) -> None:
        # Play track
        if media_type == MediaType.TRACK:
            response = await self._session.post(f'/play_track', data=media_id.encode())
            response.raise_for_status()
            return

        # Toggle playlist
        if media_type == MediaType.PLAYLIST:
            new_playlists = list(self._enabled_playlists)
            if media_id in self._enabled_playlists:
                # If playlist was enabled, disable it
                new_playlists.remove(media_id)
            else:
                # Otherwise, enable it
                new_playlists.append(media_id)

            response = await self._session.post(f'/playlists', json=new_playlists)
            response.raise_for_status()
            return

        if media_type == MediaType.PODCAST and media_id == "news":
            response = await self._session.post(f'/play_news', data=media_id.encode())
            response.raise_for_status()
            return

        raise ValueError(media_type)
