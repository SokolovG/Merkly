from src.infrastructure.fetchers.podcast.german.dw import DWPodcastFetcher
from src.infrastructure.fetchers.podcast.german.orf import ORFPodcastFetcher

# Maps language code → ordered list of fetcher classes to try first.
# Generic fetchers (iTunes, PodcastIndex) are always tried as fallback.
LANGUAGE_PODCAST_FETCHERS: dict[str, list] = {
    "de": [DWPodcastFetcher, ORFPodcastFetcher],
}
