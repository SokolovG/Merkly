from backend.src.infrastructure.fetchers.podcast.german.orf import ORFPodcastFetcher

# Maps language code → ordered list of fetcher classes to try first.
# Generic fetchers (iTunes, PodcastIndex) are always tried as fallback.
# Note: DWPodcastFetcher (rss.dw.com/xml/podcast-de-langsam) removed — feed URL dead as of 2026-04.
#       DW content is covered by DWPodcastIndexFetcher (appended in PodcastFetcherRouter.build).
LANGUAGE_PODCAST_FETCHERS: dict[str, list] = {
    "de": [ORFPodcastFetcher],
}
