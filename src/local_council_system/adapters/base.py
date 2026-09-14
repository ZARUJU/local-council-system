from __future__ import annotations

from abc import ABC, abstractmethod

from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting


class MinutesAdapter(ABC):
    @abstractmethod
    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, reference: MeetingReference) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        raise NotImplementedError
