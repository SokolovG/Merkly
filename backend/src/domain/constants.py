LANGUAGE_FLAGS: dict[str, str] = {
    "af": "🇿🇦",
    "ar": "🇸🇦",
    "az": "🇦🇿",
    "be": "🇧🇾",
    "bg": "🇧🇬",
    "bn": "🇧🇩",
    "ca": "🇪🇸",
    "cs": "🇨🇿",
    "cy": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "da": "🇩🇰",
    "de": "🇩🇪",
    "el": "🇬🇷",
    "en": "🇬🇧",
    "eo": "🌍",
    "es": "🇪🇸",
    "et": "🇪🇪",
    "eu": "🇪🇸",
    "fa": "🇮🇷",
    "fi": "🇫🇮",
    "fil": "🇵🇭",
    "fr": "🇫🇷",
    "ga": "🇮🇪",
    "gl": "🇪🇸",
    "gu": "🇮🇳",
    "he": "🇮🇱",
    "hi": "🇮🇳",
    "hr": "🇭🇷",
    "hu": "🇭🇺",
    "hy": "🇦🇲",
    "id": "🇮🇩",
    "is": "🇮🇸",
    "it": "🇮🇹",
    "ja": "🇯🇵",
    "ka": "🇬🇪",
    "kk": "🇰🇿",
    "km": "🇰🇭",
    "ko": "🇰🇷",
    "ku": "🌍",
    "ky": "🇰🇬",
    "lt": "🇱🇹",
    "lv": "🇱🇻",
    "mk": "🇲🇰",
    "ml": "🇮🇳",
    "mn": "🇲🇳",
    "ms": "🇲🇾",
    "mt": "🇲🇹",
    "my": "🇲🇲",
    "nb": "🇳🇴",
    "ne": "🇳🇵",
    "nl": "🇳🇱",
    "no": "🇳🇴",
    "pa": "🇮🇳",
    "pl": "🇵🇱",
    "pt": "🇧🇷",
    "ro": "🇷🇴",
    "ru": "🇷🇺",
    "sk": "🇸🇰",
    "sl": "🇸🇮",
    "sq": "🇦🇱",
    "sr": "🇷🇸",
    "sv": "🇸🇪",
    "sw": "🇰🇪",
    "ta": "🇮🇳",
    "te": "🇮🇳",
    "th": "🇹🇭",
    "tl": "🇵🇭",
    "tr": "🇹🇷",
    "uk": "🇺🇦",
    "ur": "🇵🇰",
    "uz": "🇺🇿",
    "vi": "🇻🇳",
    "zh": "🇨🇳",
    "zu": "🇿🇦",
}

LANGUAGE_NAMES: dict[str, str] = {
    "af": "Afrikaans",
    "ar": "Arabic",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "eo": "Esperanto",
    "es": "Spanish",
    "et": "Estonian",
    "eu": "Basque",
    "fa": "Persian",
    "fi": "Finnish",
    "fil": "Filipino",
    "fr": "French",
    "ga": "Irish",
    "gl": "Galician",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "hy": "Armenian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ka": "Georgian",
    "kk": "Kazakh",
    "km": "Khmer",
    "ko": "Korean",
    "ku": "Kurdish",
    "ky": "Kyrgyz",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mn": "Mongolian",
    "ms": "Malay",
    "mt": "Maltese",
    "my": "Burmese",
    "nb": "Norwegian Bokmål",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "zh": "Chinese",
    "zu": "Zulu",
}

DEFAULT_QUESTION_COUNT: int = 3
DEFAULT_EPISODE_DURATION_MIN: int = 3
EPISODE_DURATION_OPTIONS: list[int] = [3, 5, 7, 10]

POOL_THRESHOLD: int = 16  # Refill when pool drops below this
POOL_FILL_SIZE: int = 30  # Cards to generate per LLM batch
POOL_RECENT_HINT: int = 20  # Words passed as soft exclusion hint in LLM prompt

ARTICLE_POOL_THRESHOLD: int = 3  # refill when pool drops below this
ARTICLE_POOL_FILL_SIZE: int = 5  # articles to pre-fetch per refill batch

LISTENING_POOL_THRESHOLD: int = 2  # refill when pool drops below this
LISTENING_POOL_FILL_SIZE: int = 3  # lessons to pre-fetch per refill batch

WRITING_THEME_CHOOSE_COUNT: int = 5  # themes shown in the full picker list
WRITING_THEME_POOL_THRESHOLD: int = 8  # refill when unseen count drops below this
WRITING_THEME_FILL_SIZE: int = 15  # themes to generate per refill batch

# RSS sources per language for article fetching.
# Intentionally topic-diverse: science, culture, health, sport, and some general news.
# Hard-news-only feeds are limited to 2 per language so war/politics don't dominate.
LANG_RSS_SOURCES: dict[str, list[str]] = {
    "de": [
        "https://www.heise.de/rss/heise-top-atom.xml",  # tech
        "https://www.golem.de/rss.php",  # tech
        "https://www.spektrum.de/alias/rss/spektrum-de-rss-feed/996406",  # science
        "https://www.zeit.de/kultur/index.xml",  # culture
        "https://www.sueddeutsche.de/rss/kultur",  # culture
        "https://www.apotheken-umschau.de/feeds/rss/ratgeber",  # health
        "https://www.nationalgeographic.de/feed",  # nature
        "https://www.kicker.de/news/rss/info.xml",  # sport
        "https://www.tagesschau.de/xml/rss2/",  # general news
        "https://rss.dw.com/rdf/rss-de-news",  # general news
    ],
    "en": [
        "https://feeds.feedburner.com/TechCrunch",  # tech
        "https://www.sciencedaily.com/rss/all.xml",  # science
        "https://www.newscientist.com/feed/home/",  # science
        "https://www.theguardian.com/uk/culture/rss",  # culture
        "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",  # culture
        "https://www.health.harvard.edu/blog/feed",  # health
        "https://www.theguardian.com/environment/rss",  # environment
        "https://feeds.bbci.co.uk/sport/rss.xml",  # sport
        "https://feeds.bbci.co.uk/news/rss.xml",  # general news
        "https://rss.reuters.com/reuters/topNews",  # general news
    ],
    "es": [
        "https://www.bbc.com/mundo/ciencia_y_tecnologia/index.xml",  # science/tech
        "https://www.nationalgeographic.es/feed",  # nature
        "https://www.bbc.com/mundo/index.xml",  # general
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",  # general
    ],
    "fr": [
        "https://www.france24.com/fr/sciences-et-techno/rss",  # science/tech
        "https://www.lemonde.fr/culture/rss_full.xml",  # culture
        "https://www.france24.com/fr/rss",  # general
        "https://www.lemonde.fr/rss/une.xml",  # general
    ],
    "it": [
        "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",  # tech
        "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",  # general
    ],
    "pt": [
        "https://g1.globo.com/rss/g1/ciencia-e-saude/",  # science/health
        "https://g1.globo.com/rss/g1/",  # general
    ],
}

# Articles stripped during case-insensitive duplicate word matching.
# Covers German (der/die/das), French (le/la/un/une), Spanish (los/las), English (the).
STRIP_ARTICLES: tuple[str, ...] = (
    "der ",
    "die ",
    "das ",
    "le ",
    "la ",
    "los ",
    "las ",
    "the ",
    "un ",
    "une ",
)
